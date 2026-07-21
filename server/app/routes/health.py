import structlog
from time import monotonic

from asyncio import Lock
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db, get_redis

router = APIRouter(tags=["health"])
logger = structlog.get_logger()

_TTL = 5.0
_cache: dict = {"result": None, "ts": 0.0}
_lock = Lock()

@router.get("/health")
async def health() -> dict:
  return {"status": "ok"}

async def _run_checks(r: Redis, db: AsyncSession) -> tuple[bool, dict]:
  checks: dict[str, str] = {}

  try:
    await db.execute(text("SELECT 1"))
    checks["database"] = "ok"
  except Exception:
    logger.warning("readiness_check_failed", dependency="database", exc_info=True)
    checks["database"] = "error"

  try:
    await r.ping()
    checks["redis"] = "ok"
  except Exception:
    logger.warning("readiness_check_failed", dependency="redis", exc_info=True)
    checks["redis"] = "error"

  healthy = all(v == "ok" for v in checks.values())
  return healthy, checks

@router.get("/ready")
async def ready(
    r: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
  ) -> JSONResponse:
  now = monotonic()

  if _cache["result"] is None or now - _cache["ts"] > _TTL:
    async with _lock:
      # re-check inside lock; another request may have refreshed
      if _cache["result"] is None or monotonic() - _cache["ts"] > _TTL:
        healthy, checks = await _run_checks(r, db)
        _cache["result"] = (healthy, checks)
        _cache["ts"] = monotonic()

  healthy, checks = _cache["result"]
  return JSONResponse(
      status_code=200 if healthy else 503,
      content={"status": "ready" if healthy else "not ready", "checks": checks},
  )