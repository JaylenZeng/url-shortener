"""
Integration tests for link CRUD and the public redirect.

Covers the Week 1 deliverable checks and success criteria:
  - create link (random + custom alias)
  - custom-alias collision -> 409
  - reuse of a SOFT-DELETED alias -> allowed (partial unique index)
  - list returns only the caller's non-deleted links
  - delete is soft, and deleting someone else's link -> 404 (existence hidden)
  - redirect: 307 for live, 404 for unknown/deleted, 410 for expired
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Link
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


# ---- create -----------------------------------------------------------------

async def test_create_link_random_code(client: AsyncClient, user):
    r = await client.post(
        "/links",
        json={"original_url": "https://example.com/page"},
        headers=auth_header(user),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["short_code"]
    assert body["original_url"] == "https://example.com/page"


async def test_create_link_custom_alias(client: AsyncClient, user):
    r = await client.post(
        "/links",
        json={"original_url": "https://example.com", "custom_alias": "promo"},
        headers=auth_header(user),
    )
    assert r.status_code == 201
    assert r.json()["short_code"] == "promo"


async def test_create_link_requires_auth(client: AsyncClient):
    r = await client.post("/links", json={"original_url": "https://example.com"})
    assert r.status_code == 401


async def test_create_link_rejects_bad_url(client: AsyncClient, user):
    r = await client.post(
        "/links",
        json={"original_url": "not-a-url"},
        headers=auth_header(user),
    )
    assert r.status_code == 422


async def test_custom_alias_collision_conflicts(client: AsyncClient, user):
    payload = {"original_url": "https://example.com", "custom_alias": "taken"}
    first = await client.post("/links", json=payload, headers=auth_header(user))
    assert first.status_code == 201
    second = await client.post("/links", json=payload, headers=auth_header(user))
    assert second.status_code == 409


async def test_deleted_alias_can_be_reused(client: AsyncClient, user):
    """The partial unique index (WHERE deleted_at IS NULL) frees a code once its
    link is soft-deleted."""
    payload = {"original_url": "https://example.com", "custom_alias": "recycle"}
    created = await client.post("/links", json=payload, headers=auth_header(user))
    link_id = created.json()["id"]

    deleted = await client.delete(f"/links/{link_id}", headers=auth_header(user))
    assert deleted.status_code == 204

    # Same alias again -> should now succeed, not 409.
    again = await client.post("/links", json=payload, headers=auth_header(user))
    assert again.status_code == 201
    assert again.json()["short_code"] == "recycle"


# ---- list -------------------------------------------------------------------

async def test_list_returns_only_own_links(client: AsyncClient, user, other_user):
    await client.post(
        "/links", json={"original_url": "https://a.com"}, headers=auth_header(user)
    )
    await client.post(
        "/links", json={"original_url": "https://b.com"}, headers=auth_header(other_user)
    )
    r = await client.get("/links", headers=auth_header(user))
    assert r.status_code == 200
    urls = [link["original_url"] for link in r.json()]
    assert "https://a.com/" in urls
    assert "https://b.com" not in urls  # other user's link not visible


async def test_list_excludes_deleted(client: AsyncClient, user):
    created = await client.post(
        "/links", json={"original_url": "https://gone.com"}, headers=auth_header(user)
    )
    link_id = created.json()["id"]
    await client.delete(f"/links/{link_id}", headers=auth_header(user))

    r = await client.get("/links", headers=auth_header(user))
    urls = [link["original_url"] for link in r.json()]
    assert "https://gone.com" not in urls


# ---- delete -----------------------------------------------------------------

async def test_delete_is_soft(client: AsyncClient, user, db: AsyncSession):
    """Row survives with deleted_at set — history retained."""
    created = await client.post(
        "/links", json={"original_url": "https://keep.com"}, headers=auth_header(user)
    )
    link_id = created.json()["id"]
    await client.delete(f"/links/{link_id}", headers=auth_header(user))

    row = await db.scalar(select(Link).where(Link.id == link_id))
    assert row is not None            # not physically removed
    assert row.deleted_at is not None  # marked deleted


async def test_delete_other_users_link_404(client: AsyncClient, user, other_user):
    """Existence is hidden: deleting a link you don't own returns 404, not 403."""
    created = await client.post(
        "/links", json={"original_url": "https://mine.com"}, headers=auth_header(user)
    )
    link_id = created.json()["id"]
    r = await client.delete(f"/links/{link_id}", headers=auth_header(other_user))
    assert r.status_code == 404


async def test_delete_nonexistent_404(client: AsyncClient, user):
    import uuid
    r = await client.delete(f"/links/{uuid.uuid4()}", headers=auth_header(user))
    assert r.status_code == 404


# ---- redirect (public) ------------------------------------------------------

async def test_redirect_live_link_307(client: AsyncClient, user):
    created = await client.post(
        "/links",
        json={"original_url": "https://target.com", "custom_alias": "goto"},
        headers=auth_header(user),
    )
    assert created.status_code == 201
    # Don't auto-follow: assert on the 307 and Location header itself.
    r = await client.get("/goto", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://target.com/"  # HttpUrl adds trailing slash


async def test_redirect_unknown_code_404(client: AsyncClient):
    r = await client.get("/doesnotexist", follow_redirects=False)
    assert r.status_code == 404


async def test_redirect_deleted_link_404(client: AsyncClient, user):
    created = await client.post(
        "/links",
        json={"original_url": "https://x.com", "custom_alias": "dead"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]
    await client.delete(f"/links/{link_id}", headers=auth_header(user))
    r = await client.get("/dead", follow_redirects=False)
    assert r.status_code == 404


async def test_redirect_expired_link_410(client: AsyncClient, user, db: AsyncSession):
    """Create a link, then set expires_at in the past directly, and expect 410."""
    created = await client.post(
        "/links",
        json={"original_url": "https://old.com", "custom_alias": "expired"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]

    row = await db.scalar(select(Link).where(Link.id == link_id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    r = await client.get("/expired", follow_redirects=False)
    assert r.status_code == 410


async def test_redirect_permanent_link_does_not_crash(client: AsyncClient, user):
    """Regression: expires_at IS NULL must not raise (the None-comparison bug)."""
    await client.post(
        "/links",
        json={"original_url": "https://perm.com", "custom_alias": "perm"},
        headers=auth_header(user),
    )
    r = await client.get("/perm", follow_redirects=False)
    assert r.status_code == 307
