"""
Shared pytest fixtures for the URL shortener test suite.

IMPORTANT — test database:
  These integration tests CREATE and DROP tables. Point them at a
  DEDICATED test database, never your dev DB. Set TEST_DATABASE_URL, e.g.:

    export TEST_DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener_test"

  Create the DB once:
    docker compose exec db psql -U postgres -c "CREATE DATABASE urlshortener_test;"

Run:
    uv run pytest -v
"""
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import fakeredis.aioredis
 
from app.main import app
from app.core.config import settings
from app.core.db import get_db, get_redis, get_arq
from app.models import Base, User
from app.services.auth_service import hash_password, create_access_token


@pytest.fixture(autouse=True)
def _no_live_dns():
    """Don't let the email-deliverability MX lookup reach real DNS in tests.
    Tests that exercise it flip the flag back on and stub the resolver."""
    settings.verify_email_deliverability = False
    yield

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/urlshortener_test",
)

# NullPool so each test gets clean connections; echo off to keep output readable.
engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    """Fresh schema per test — full isolation. Slower than savepoints, but simple
    and bulletproof for a warmup project."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """A session for tests that need to touch the DB directly (seeding, assertions)."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncSession, None]:
    """Async HTTP client wired to the app, with get_db overridden to the test DB.

    The override mirrors the real commit-owning get_db: commit on clean exit,
    rollback on exception."""
    async def _override_get_db():
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ---- auth helpers -----------------------------------------------------------

@pytest_asyncio.fixture
async def user(db: AsyncSession) -> User:
    """A persisted user with a known password."""
    u = User(email="alice@example.com", password_hash=hash_password("password123"))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def other_user(db: AsyncSession) -> User:
    u = User(email="bob@example.com", password_hash=hash_password("password123"))
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


def auth_header(u: User) -> dict[str, str]:
    """Bearer header for a given user."""
    token = create_access_token(str(u.id))
    return {"Authorization": f"Bearer {token}"}

# ---- fake Redis -------------------------------------------------------------
 
@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator["fakeredis.aioredis.FakeRedis", None]:
    """In-process Redis. decode_responses=True to match the real client, so
    cached values come back as str (your sentinels + json.loads rely on this)."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await r.flushall()
    yield r
    await r.flushall()
    await r.aclose()
 
 
# ---- spy arq pool -----------------------------------------------------------
 
class SpyArq:
    """Stand-in for the arq pool. Records enqueue_job calls instead of queueing.
 
    Tests assert on `.jobs` to prove the redirect enqueued a click without
    needing a live Redis queue or a worker process.
    """
    def __init__(self):
        self.jobs: list[tuple[str, tuple, dict]] = []
        self.fail = False  # flip to simulate an enqueue failure
 
    async def enqueue_job(self, name, *args, **kwargs):
        if self.fail:
            raise RuntimeError("simulated enqueue failure")
        self.jobs.append((name, args, kwargs))
        return object()  # arq returns a Job; identity is all we need
 
 
@pytest_asyncio.fixture
async def spy_arq() -> AsyncGenerator[SpyArq, None]:
    yield SpyArq()
 
 
# ---- wire the overrides -----------------------------------------------------
 
@pytest_asyncio.fixture(autouse=True)
async def _override_redis_and_arq(fake_redis, spy_arq):
    """Point the app's get_redis / get_arq at the fakes for every Week 2 test.
    autouse so the redirect route always gets them; harmless for Week 1 tests
    (they simply don't hit these dependencies)."""
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_arq] = lambda: spy_arq
    yield
    app.dependency_overrides.pop(get_redis, None)
    app.dependency_overrides.pop(get_arq, None)
