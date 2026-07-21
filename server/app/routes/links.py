import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.limiter import limiter, user_or_ip_key
from app.db import get_db
from app.models import Link, User
from app.schemas.links import CreateLinkRequest, LinkResponse
from app.services.auth_service import get_current_user
from app.services.link_service import create_link_service, delete_link_service

router = APIRouter(prefix="/links", tags=["links"])

# Create a link
@router.post("", status_code=201, response_model=LinkResponse)
@limiter.limit("1000000/minute", key_func=user_or_ip_key)
async def create_link(body: CreateLinkRequest, request: Request, db: AsyncSession = Depends(get_db), curr_user: User = Depends(get_current_user)) -> Link:
  link = await create_link_service(db, curr_user, body.original_url, body.custom_alias, body.expires_at)
  return link

# Get all of a user's links
@router.get("", status_code=200, response_model=list[LinkResponse])
async def list_links(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)) -> list[Link]:
  results = await db.scalars(select(Link).where(Link.user_id == user.id, Link.deleted_at.is_(None)))
  return results.all()

# Delete a user's links
@router.delete("/{link_id}", status_code=204)
async def delete_link(link_id: uuid.UUID, db: AsyncSession = Depends(get_db), curr_user: User = Depends(get_current_user)) -> None:
  await delete_link_service(db, curr_user, link_id)
