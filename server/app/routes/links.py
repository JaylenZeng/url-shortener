import uuid

from fastapi import APIRouter, Depends, Request
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.limiter import limiter, user_or_ip_key
from app.core.db import get_db, get_redis
from app.models import ClickEvent, Link, User
from app.schemas.links import CreateLinkRequest, LinkResponse, LinkStatsResponse
from app.services.auth_service import get_current_user
from app.services.link_service import (
  create_link_service,
  delete_link_service,
  get_link_stats_service,
)

router = APIRouter(prefix="/links", tags=["links"])

# Create a link
@router.post("", status_code=201, response_model=LinkResponse)
@limiter.limit("10/minute", key_func=user_or_ip_key)
async def create_link(body: CreateLinkRequest, request: Request, db: AsyncSession = Depends(get_db), curr_user: User = Depends(get_current_user)) -> Link:
  link = await create_link_service(db, curr_user, body.original_url, body.custom_alias, body.expires_at)
  return link

# Get all of a user's links, newest first, each with its total click count.
@router.get("", status_code=200, response_model=list[LinkResponse])
async def list_links(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)) -> list[LinkResponse]:
  clicks = (
    select(ClickEvent.link_id, func.count().label("clicks"))
    .group_by(ClickEvent.link_id)
    .subquery()
  )
  stmt = (
    select(Link, func.coalesce(clicks.c.clicks, 0))
    .outerjoin(clicks, clicks.c.link_id == Link.id)
    .where(Link.user_id == user.id, Link.deleted_at.is_(None))
    .order_by(Link.created_at.desc())
  )
  rows = await db.execute(stmt)
  return [
    LinkResponse(
      id=link.id,
      short_code=link.short_code,
      original_url=link.original_url,
      created_at=link.created_at,
      expires_at=link.expires_at,
      click_count=count,
    )
    for link, count in rows.all()
  ]

# Analytics for a single link: clicks by day, top referrers, top user agents.
@router.get("/{link_id}/stats", status_code=200, response_model=LinkStatsResponse)
async def link_stats(
  link_id: uuid.UUID,
  db: AsyncSession = Depends(get_db),
  curr_user: User = Depends(get_current_user),
) -> LinkStatsResponse:
  return await get_link_stats_service(db, curr_user, link_id)

# Delete a user's links
@router.delete("/{link_id}", status_code=204)
async def delete_link(
  link_id: uuid.UUID, 
  db: AsyncSession = Depends(get_db), 
  r: Redis = Depends(get_redis), 
  curr_user: User = Depends(get_current_user)
) -> None:
  await delete_link_service(db, curr_user, link_id, r)
