from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from arq.connections import RedisSettings

from app.models import ClickEvent
from app.schemas.redirect import ClickEventPayload

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def record_click(ctx, payload: ClickEventPayload):
  click_event = ClickEvent(
    link_id=payload.link_id,
    timestamp=payload.clicked_at,
    user_agent=payload.user_agent, 
    referrer=payload.referrer,
    ip=payload.ip
  )
  AsyncSessionLocal = ctx["db"]
  async with AsyncSessionLocal() as session:
    try:
      session.add(click_event)
      await session.commit()
    except Exception:
      await session.rollback()
      raise
  
async def startup(ctx):
  # async with SessionLocal() as session:
  #   try:
  #     yield session
  #     await session.commit()
  #   except Exception:
  #     await session.rollback()
  #     raise
  ctx["db"] = SessionLocal


async def shutdown(ctx):
  await engine.dispose()

class WorkerSettings:
  functions = [record_click]  

  # Lifecycle hooks
  on_startup = startup
  on_shutdown = shutdown
  
  # Redis configuration (defaults to localhost:6379 if omitted)
  redis_settings = RedisSettings(host='127.0.0.1', port=6379)
  
  