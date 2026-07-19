import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db, get_redis
from app.schemas.redirect import ClickEventPayload
from app.services.redirect_service import LinkData, resolve_url
from datetime import datetime, timezone

router = APIRouter(tags=["redirect"])
logger = logging.getLogger(__name__)

# Redirects person who clicked on link to original URL
@router.get("/{code}")
async def redirect_link(code: str, request: Request, r: Redis = Depends(get_redis), db: AsyncSession = Depends(get_db)):
  data: LinkData = await resolve_url(code, r, db)
  payload = {
    "link_id": data["link_id"],
    "clicked_at": datetime.now(timezone.utc),
    "user_agent": request.headers.get("user-agent"),
    "referrer": request.headers.get("referer"),
    "ip": request.client.host
  }
  try:
    await r.enqueue_job("record_click", payload)
  except Exception:
    # TODO: structlog.warning("click enqueue failed", code=code)
    logger.warning("click enqueue failed for code %s", code)
  return RedirectResponse(url=data["url"], status_code=307)

