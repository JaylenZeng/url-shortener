"""
Caching behaviour on the public redirect.

Covers the cache-aside deliverable and its success criteria:
  - cold hit populates the cache (positive entry, JSON payload, capped TTL)
  - warm hit is served from cache and does NOT touch the DB
  - unknown code writes a __MISS__ sentinel with a SHORT ttl (negative cache)
  - expired link writes an __EXPIRED__ sentinel and returns 410
  - delete invalidates the cache key (no resurrection of a dead link)

These assert on Redis state directly via the `fake_redis` fixture, so we can
see the exact keys/TTLs your resolve_url/fetch_link produce.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Link
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


# ---- positive cache ---------------------------------------------------------

async def test_cold_hit_populates_cache(client: AsyncClient, user, fake_redis):
    """First redirect is a cache miss -> DB read -> Redis populated with JSON."""
    await client.post(
        "/links",
        json={"original_url": "https://target.com", "custom_alias": "cold"},
        headers=auth_header(user),
    )
    # nothing cached yet
    assert await fake_redis.get("link:cold") is None

    r = await client.get("/cold", follow_redirects=False)
    assert r.status_code == 307

    cached = await fake_redis.get("link:cold")
    assert cached is not None
    payload = json.loads(cached)
    assert payload["url"] == "https://target.com/"
    assert "link_id" in payload  # id cached so click events can key off it


async def test_cached_ttl_capped_at_default(client: AsyncClient, user, fake_redis):
    """A permanent link (no expiry) caches with the 1h default TTL."""
    await client.post(
        "/links",
        json={"original_url": "https://perm.com", "custom_alias": "ttl"},
        headers=auth_header(user),
    )
    await client.get("/ttl", follow_redirects=False)
    ttl = await fake_redis.ttl("link:ttl")
    assert 0 < ttl <= 3600


async def test_ttl_capped_below_expiry(client: AsyncClient, user, db: AsyncSession):
    """If the link expires in 10 min, cache TTL must not exceed that — otherwise
    a stale-but-cached link would keep redirecting past its expiry."""
    created = await client.post(
        "/links",
        json={"original_url": "https://soon.com", "custom_alias": "shortlived"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]
    row = await db.scalar(select(Link).where(Link.id == link_id))
    row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await db.commit()

    # need the fixture's redis to inspect ttl; pull it via a fresh hit
    # (route uses the overridden fake_redis)
    from app.main import app
    from app.core.db import get_redis
    r = app.dependency_overrides[get_redis]()

    await client.get("/shortlived", follow_redirects=False)
    ttl = await r.ttl("link:shortlived")
    assert 0 < ttl <= 600  # capped to the ~10 min remaining, not 3600


async def test_warm_hit_served_from_cache(client: AsyncClient, user, fake_redis, db):
    """Second hit reads from cache. We prove it by poisoning the cache with a
    different URL. If the response follows the poisoned value, it came from
    Redis, not the DB."""
    await client.post(
        "/links",
        json={"original_url": "https://real.com", "custom_alias": "warm"},
        headers=auth_header(user),
    )
    # first hit populates
    await client.get("/warm", follow_redirects=False)

    # overwrite cache with a decoy payload
    poisoned = json.dumps({"url": "https://cache-was-used.com/", "link_id": str(uuid.uuid4())})
    await fake_redis.set("link:warm", poisoned)

    r = await client.get("/warm", follow_redirects=False)
    assert r.headers["location"] == "https://cache-was-used.com/"


# ---- negative cache ---------------------------------------------------------

async def test_unknown_code_caches_miss_sentinel(client: AsyncClient, fake_redis):
    """Unknown code -> 404 AND a __MISS__ sentinel so repeated hits on a bogus
    code don't hammer Postgres (cache-penetration defence)."""
    r = await client.get("/nope", follow_redirects=False)
    assert r.status_code == 404

    cached = await fake_redis.get("link:nope")
    assert cached == "__MISS__"


async def test_miss_sentinel_has_short_ttl(client: AsyncClient, fake_redis):
    """Negative TTL must be short (~60s), so a code created moments later isn't
    shadowed by a stale 'does not exist' for an hour."""
    await client.get("/nope2", follow_redirects=False)
    ttl = await fake_redis.ttl("link:nope2")
    assert 0 < ttl <= 60


async def test_cached_miss_returns_404_without_db(client: AsyncClient, fake_redis):
    """A pre-seeded __MISS__ short-circuits to 404 straight from cache."""
    await fake_redis.set("link:preseeded", "__MISS__", ex=60)
    r = await client.get("/preseeded", follow_redirects=False)
    assert r.status_code == 404


async def test_expired_link_caches_expired_sentinel(
    client: AsyncClient, user, db: AsyncSession, fake_redis
):
    """Expired link -> 410 AND an __EXPIRED__ sentinel (distinct from __MISS__,
    because the two map to different status codes: 410 vs 404)."""
    created = await client.post(
        "/links",
        json={"original_url": "https://old.com", "custom_alias": "expsent"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]
    row = await db.scalar(select(Link).where(Link.id == link_id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    r = await client.get("/expsent", follow_redirects=False)
    assert r.status_code == 410
    assert await fake_redis.get("link:expsent") == "__EXPIRED__"


async def test_cached_expired_returns_410(client: AsyncClient, fake_redis):
    """Pre-seeded __EXPIRED__ short-circuits to 410 from cache."""
    await fake_redis.set("link:preexp", "__EXPIRED__", ex=60)
    r = await client.get("/preexp", follow_redirects=False)
    assert r.status_code == 410


# ---- invalidation -----------------------------------------------------------

async def test_delete_invalidates_cache(client: AsyncClient, user, fake_redis):
    """After a link is cached then deleted, the cache key must be gone — a
    subsequent read must not resurrect the dead link from a stale entry."""
    created = await client.post(
        "/links",
        json={"original_url": "https://killme.com", "custom_alias": "killme"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]

    # populate cache
    await client.get("/killme", follow_redirects=False)
    assert await fake_redis.get("link:killme") is not None

    # delete should invalidate
    await client.delete(f"/links/{link_id}", headers=auth_header(user))
    assert await fake_redis.get("link:killme") is None

    # and the next read is a clean 404 (soft-deleted -> not found)
    r = await client.get("/killme", follow_redirects=False)
    assert r.status_code == 404
