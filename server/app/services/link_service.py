from datetime import datetime
import secrets, string
import uuid
from pydantic import HttpUrl
from redis import Redis
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import ClickEvent, Link, User
from app.core.exceptions import AliasTakenError, CodeGenerationError
from app.core.exceptions import LinkNotFoundError
from app.schemas.links import (
  DailyClicks,
  LinkStatsResponse,
  ReferrerCount,
  UserAgentCount,
)

ALPHABET = string.ascii_letters + string.digits

def generate_code(length: int = 7) -> str:
  return "".join(secrets.choice(ALPHABET) for _ in range(length))

async def create_link_service(db: AsyncSession, user: User, original_url: HttpUrl, custom_alias: str | None, expiration: datetime | None = None) -> Link:
  code = custom_alias or generate_code()
  for _ in range(5):
    link = Link(
      short_code=code, 
      original_url=str(original_url), 
      user_id=user.id, 
      expires_at=expiration
    )
    db.add(link)
    try:
      await db.flush()
      return link
    except IntegrityError as e:
      await db.rollback()
      constraint = getattr(getattr(e.orig, "__cause__", None), "constraint_name", None)
      if constraint == "ix_links_short_code_active": 
        if custom_alias:          
          raise AliasTakenError()
        code = generate_code()
        continue
      raise # not our concern, let it surface as a real error
  raise CodeGenerationError()

async def delete_link_service(db: AsyncSession, user: User, link_id: uuid.UUID, r: Redis):
  link = await db.scalar(
    select(Link).where(
      Link.id == link_id,
      Link.user_id == user.id,
      Link.deleted_at.is_(None)
    )
  )
  if link is None:
    raise LinkNotFoundError()
  link.deleted_at = func.now()
  await db.flush()
  await r.delete(f"link:{link.short_code}")
  

async def get_link_stats_service(
  db: AsyncSession, user: User, link_id: uuid.UUID, top_n: int = 10
) -> LinkStatsResponse:
  # Ensure the link exists and belongs to this user before exposing its stats.
  link = await db.scalar(
    select(Link).where(
      Link.id == link_id,
      Link.user_id == user.id,
      Link.deleted_at.is_(None),
    )
  )
  if link is None:
    raise LinkNotFoundError()

  clicks = func.count().label("clicks")

  day = func.date(ClickEvent.timestamp).label("day")
  by_day = (
    await db.execute(
      select(day, clicks)
      .where(ClickEvent.link_id == link_id)
      .group_by(day)
      .order_by(day)
    )
  ).all()

  referrers = (
    await db.execute(
      select(ClickEvent.referrer, clicks)
      .where(ClickEvent.link_id == link_id)
      .group_by(ClickEvent.referrer)
      .order_by(clicks.desc())
      .limit(top_n)
    )
  ).all()

  user_agents = (
    await db.execute(
      select(ClickEvent.user_agent, clicks)
      .where(ClickEvent.link_id == link_id)
      .group_by(ClickEvent.user_agent)
      .order_by(clicks.desc())
      .limit(top_n)
    )
  ).all()

  return LinkStatsResponse(
    link_id=link.id,
    short_code=link.short_code,
    total_clicks=sum(count for _, count in by_day),
    clicks_by_day=[DailyClicks(date=d, clicks=count) for d, count in by_day],
    top_referrers=[ReferrerCount(referrer=r, clicks=count) for r, count in referrers],
    top_user_agents=[
      UserAgentCount(user_agent=ua, clicks=count) for ua, count in user_agents
    ],
  )


async def get_active_link_by_code(db: AsyncSession, code: str) -> Link | None:
  return await db.scalar(
      select(Link).where(
          Link.short_code == code,
          Link.deleted_at.is_(None),
      )
  )