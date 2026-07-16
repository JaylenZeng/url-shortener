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
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.db import get_db
from app.models import Base, User
from app.services.auth_service import hash_password, create_access_token

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
