
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, get_redis
from app.exceptions import LinkNotFoundError, LinkExpiredError
from app.services.link_service import get_active_link_by_code

async def fetch_link(code: str, r: Redis, db: AsyncSession):
  link = await get_active_link_by_code(db, code)
  
  # check if result is valid
  if link is None:
    await r.set(f"link:{code}", "__MISS__", ex=60)  # short TTL
    raise LinkNotFoundError()
  if link.expires_at is not None and link.expires_at < datetime.now(timezone.utc):
    await r.set(f"link:{code}", "__EXPIRED__", ex=60)
    raise LinkExpiredError() # don't cache —> already dead

  ttl = 3600
  if link.expires_at:
      remaining = int((link.expires_at - datetime.now(timezone.utc)).total_seconds())
      ttl = min(ttl, remaining)
  await r.set(f"link:{code}", link.original_url, ex=ttl)
  return link.original_url

async def resolve_url(code: str, r: Redis, db: AsyncSession) -> str:
  cached = await r.get(f"link:{code}")
  # cache hit!
  if cached == "__MISS__":
    raise LinkNotFoundError()
  if cached == "__EXPIRED__":
    raise LinkExpiredError()
  if cached:
    return cached

  # cache miss...
  return await fetch_link(code, r, db)