from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from redis import Redis
from arq import create_pool
from arq.connections import RedisSettings
import redis.asyncio as redis


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)
_arq_pool = None

async def get_redis() -> Redis:
  return redis.Redis(connection_pool=pool)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
  async with SessionLocal() as session:
    try:
      yield session
      await session.commit()
    except Exception:
      await session.rollback()
      raise

async def init_arq_pool():
  global _arq_pool
  _arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

async def close_arq_pool():
  global _arq_pool
  if _arq_pool:
    await _arq_pool.close()

async def get_arq():
  if _arq_pool is None:
    raise RuntimeError("arq pool not initialized - check lifespan startup")
  return _arq_pool