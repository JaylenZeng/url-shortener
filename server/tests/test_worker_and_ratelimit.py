"""
worker idempotency + rate limiting.

Two independent concerns:

1. record_click idempotency (the ON CONFLICT DO NOTHING guard)
   - inserting the SAME event_id twice yields ONE row, not two
   - distinct event_ids yield distinct rows
   This is what makes an arq retry (after a crash mid-job) safe: the retry
   replays the same event_id and the second insert no-ops.

2. Rate limiting
   - a per-IP limit on the redirect returns 429 once exceeded
   NOTE: these depend on real limits + a storage backend. See the skip guard.

The worker tests call record_click directly with a hand-built ctx, so no arq
runtime or Redis queue is needed — just the DB.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClickEvent, Link, User
from app.worker import record_click
from tests.conftest import TestSessionLocal, auth_header

pytestmark = pytest.mark.asyncio


async def _seed_link(db: AsyncSession) -> Link:
    """A link to attach clicks to (FK requires a real link + user)."""
    u = User(email=f"{uuid.uuid4()}@x.com", password_hash="x")
    db.add(u)
    await db.flush()
    link = Link(short_code=uuid.uuid4().hex[:8], original_url="https://x.com", user_id=u.id)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


def _payload(link_id, event_id):
    return {
        "link_id": str(link_id),
        "event_id": str(event_id),
        "clicked_at": datetime.now(timezone.utc).isoformat(),
        "user_agent": "test",
        "referrer": None,
        "ip": "1.2.3.4",
    }


# ---- idempotency ------------------------------------------------------------

async def test_record_click_inserts_row(db: AsyncSession):
    link = await _seed_link(db)
    ctx = {"db": TestSessionLocal}
    await record_click(ctx, _payload(link.id, uuid.uuid4()))

    count = await db.scalar(select(func.count()).select_from(ClickEvent))
    assert count == 1


async def test_duplicate_event_id_is_deduped(db: AsyncSession):
    """Same event_id twice -> exactly one row. This is the arq-retry safety net:
    a job re-run after a crash carries the same event_id and must not double-count."""
    link = await _seed_link(db)
    ctx = {"db": TestSessionLocal}
    fixed = uuid.uuid4()

    await record_click(ctx, _payload(link.id, fixed))
    await record_click(ctx, _payload(link.id, fixed))  # retry / duplicate

    count = await db.scalar(
        select(func.count()).select_from(ClickEvent).where(ClickEvent.event_id == fixed)
    )
    assert count == 1


async def test_distinct_event_ids_insert_separately(db: AsyncSession):
    link = await _seed_link(db)
    ctx = {"db": TestSessionLocal}

    await record_click(ctx, _payload(link.id, uuid.uuid4()))
    await record_click(ctx, _payload(link.id, uuid.uuid4()))

    count = await db.scalar(select(func.count()).select_from(ClickEvent))
    assert count == 2


async def test_recorded_click_preserves_click_time(db: AsyncSession):
    """clicked_at from the payload is stored, NOT the worker's write time —
    so a backlogged queue doesn't smear all clicks to drain-time."""
    link = await _seed_link(db)
    ctx = {"db": TestSessionLocal}
    click_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    payload = _payload(link.id, uuid.uuid4())
    payload["clicked_at"] = click_time.isoformat()
    await record_click(ctx, payload)

    row = await db.scalar(select(ClickEvent))
    assert row.timestamp == click_time


# ---- rate limiting ----------------------------------------------------------

async def test_redirect_rate_limited(client, user):
    """After exceeding the per-IP limit, further redirects get 429."""
    await client.post(
        "/links",
        json={"original_url": "https://rl.com", "custom_alias": "rl"},
        headers=auth_header(user),
    )
    statuses = []
    for _ in range(150):  # over a 100/min limit
        r = await client.get("/rl", follow_redirects=False)
        statuses.append(r.status_code)
    assert 429 in statuses

async def test_create_link_rate_limited_per_user(client, user):
    """POST /links throttles per user; the 11th create in a window -> 429."""
    statuses = []
    for i in range(12):  # over a 10/min limit
        r = await client.post(
            "/links",
            json={"original_url": f"https://rl.com/{i}"},
            headers=auth_header(user),
        )
        statuses.append(r.status_code)
    assert 429 in statuses
