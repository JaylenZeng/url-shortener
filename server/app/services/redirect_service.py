
from datetime import datetime, timezone
import json
from typing import TypedDict

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import LinkNotFoundError, LinkExpiredError
from app.services.link_service import get_active_link_by_code

class LinkData(TypedDict):
    url: str
    link_id: str

async def fetch_link(code: str, r: Redis, db: AsyncSession) -> LinkData:
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
  data = {
    "url": link.original_url,
    "link_id": str(link.id)
  }
  await r.set(f"link:{code}", json.dumps(data), ex=ttl)
  return data

async def resolve_url(code: str, r: Redis, db: AsyncSession) -> LinkData:
  cached = await r.get(f"link:{code}")
  # cache hit!
  if cached == "__MISS__":
    raise LinkNotFoundError()
  if cached == "__EXPIRED__":
    raise LinkExpiredError()
  if cached:
    return json.loads(cached)

  # cache miss...
  return await fetch_link(code, r, db)