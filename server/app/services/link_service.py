from datetime import datetime
import secrets, string
import uuid
from pydantic import HttpUrl
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Link, User
from app.exceptions import AliasTakenError, CodeGenerationError
from app.exceptions import LinkNotFoundError

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

async def delete_link_service(db: AsyncSession, user: User, link_id: uuid.UUID):
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

async def get_active_link_by_code(db: AsyncSession, code: str) -> Link | None:
  return await db.scalar(
      select(Link).where(
          Link.short_code == code,
          Link.deleted_at.is_(None),
      )
  )