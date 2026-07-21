import structlog
from structlog.contextvars import get_contextvars
import uuid

from arq import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_arq, get_db, get_redis
from app.schemas.redirect import ClickEventPayload
from app.services.redirect_service import LinkData, resolve_url
from datetime import datetime, timezone
from app.core.limiter import limiter
from structlog.contextvars import get_contextvars

router = APIRouter(tags=["redirect"])
logger = structlog.get_logger()  

# Redirects person who clicked on link to original URL
@router.get("/{code}")
@limiter.limit("100/minute")
async def redirect_link(
    code: str, request: Request, 
    r: Redis = Depends(get_redis), 
    db: AsyncSession = Depends(get_db),
    arq: ArqRedis = Depends(get_arq)
  ):
  data: LinkData = await resolve_url(code, r, db)
  this_event_id = uuid.uuid4()
  rid = get_contextvars().get("request_id")
  try:
    payload = ClickEventPayload(
      link_id=data["link_id"],
      event_id=this_event_id,
      request_id=rid,
      clicked_at=datetime.now(timezone.utc),
      user_agent=request.headers.get("user-agent"),
      referrer=request.headers.get("referer"),
      ip=request.client.host,
    )
    await arq.enqueue_job("record_click", payload.model_dump(mode="json"))
    logger.info("click_enqueued", code=code, event_id=str(this_event_id))
  except Exception:
    logger.warning("click_enqueue_failed", code=code, exc_info=True)
  return RedirectResponse(url=data["url"], status_code=307)

