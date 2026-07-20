from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.config import settings
from arq.connections import RedisSettings

from app.models import ClickEvent
from app.schemas.redirect import ClickEventPayload

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def record_click(ctx, raw: dict):
  payload = ClickEventPayload.model_validate(raw)
  stmt = pg_insert(ClickEvent).values(
    link_id=payload.link_id,
    event_id=payload.event_id,
    timestamp=payload.clicked_at,
    user_agent=payload.user_agent, 
    referrer=payload.referrer,
    ip=payload.ip
  ).on_conflict_do_nothing(index_elements=["event_id"])
  
  AsyncSessionLocal = ctx["db"]
  async with AsyncSessionLocal() as session:
    try:
      result = await session.execute(stmt)
      # result.rowcount == 0 means it's a duplicate
      await session.commit()
    except Exception:
      await session.rollback()
      raise
  
  # return "ok"
  
async def startup(ctx):
  ctx["db"] = SessionLocal

async def shutdown(ctx):
  await engine.dispose()

class WorkerSettings:
  functions = [record_click]  

  # Lifecycle hooks
  on_startup = startup
  on_shutdown = shutdown
  
  # Redis configuration (defaults to localhost:6379 if omitted)
  redis_settings = RedisSettings.from_dsn(settings.redis_url)
  
  