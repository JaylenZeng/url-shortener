"""
Click-event queueing on redirect.

Covers the async-analytics deliverable:
  - a successful redirect enqueues exactly one `record_click` job
  - the enqueued payload carries link_id, an event_id, a UTC clicked_at, and
    the request metadata (user_agent, referrer, ip)
  - the payload is JSON-serialisable primitives (model_dump(mode="json")),
    NOT a raw datetime/UUID — this is what survives the Redis round-trip
  - dead-link redirects (404/410) do NOT enqueue a click
  - an enqueue failure is swallowed: the user still gets their redirect
    (analytics is best-effort; a logging problem must not break the hot path)

Uses the SpyArq fixture: we assert on what WOULD be queued without a worker.
"""
import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


async def test_redirect_enqueues_one_click(client: AsyncClient, user, spy_arq):
    await client.post(
        "/links",
        json={"original_url": "https://target.com", "custom_alias": "click1"},
        headers=auth_header(user),
    )
    r = await client.get("/click1", follow_redirects=False)
    assert r.status_code == 307

    assert len(spy_arq.jobs) == 1
    name, args, kwargs = spy_arq.jobs[0]
    assert name == "record_click"


async def test_enqueued_payload_shape(client: AsyncClient, user, spy_arq):
    """Payload must be JSON primitives and carry all analytics fields."""
    await client.post(
        "/links",
        json={"original_url": "https://target.com", "custom_alias": "click2"},
        headers=auth_header(user),
    )
    await client.get(
        "/click2",
        follow_redirects=False,
        headers={"user-agent": "pytest-agent", "referer": "https://ref.com"},
    )

    _, args, _ = spy_arq.jobs[0]
    payload = args[0]  # enqueue_job("record_click", payload)

    assert isinstance(payload, dict)
    # link_id + event_id present and string-serialised (JSON-safe)
    assert isinstance(payload["link_id"], str)
    assert isinstance(payload["event_id"], str)
    # event_id is a valid uuid string
    uuid.UUID(payload["event_id"])
    # clicked_at is an ISO string, not a datetime object
    assert isinstance(payload["clicked_at"], str)
    datetime.fromisoformat(payload["clicked_at"])  # parses -> valid ISO
    # request metadata captured
    assert payload["user_agent"] == "pytest-agent"
    assert payload["referrer"] == "https://ref.com"
    assert payload["ip"]  # some client host recorded


async def test_each_redirect_gets_unique_event_id(client: AsyncClient, user, spy_arq):
    """event_id is generated per click -> two redirects, two distinct ids.
    (Idempotency dedupes RETRIES of the same job, not distinct clicks.)"""
    await client.post(
        "/links",
        json={"original_url": "https://target.com", "custom_alias": "click3"},
        headers=auth_header(user),
    )
    await client.get("/click3", follow_redirects=False)
    await client.get("/click3", follow_redirects=False)

    ids = [args[0]["event_id"] for _, args, _ in spy_arq.jobs]
    assert len(ids) == 2
    assert ids[0] != ids[1]


async def test_unknown_code_does_not_enqueue(client: AsyncClient, spy_arq):
    """A 404 must not record a click — nothing was actually visited."""
    r = await client.get("/ghost", follow_redirects=False)
    assert r.status_code == 404
    assert spy_arq.jobs == []


async def test_expired_link_does_not_enqueue(
    client: AsyncClient, user, spy_arq, db
):
    """A 410 must not record a click."""
    from datetime import timedelta, timezone
    from sqlalchemy import select
    from app.models import Link

    created = await client.post(
        "/links",
        json={"original_url": "https://old.com", "custom_alias": "expnoq"},
        headers=auth_header(user),
    )
    link_id = created.json()["id"]
    row = await db.scalar(select(Link).where(Link.id == link_id))
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db.commit()

    r = await client.get("/expnoq", follow_redirects=False)
    assert r.status_code == 410
    assert spy_arq.jobs == []


async def test_enqueue_failure_still_redirects(client: AsyncClient, user, spy_arq):
    """If enqueue raises, the redirect must still succeed (best-effort analytics).
    The hot path cannot fail because a background-logging write failed."""
    await client.post(
        "/links",
        json={"original_url": "https://resilient.com", "custom_alias": "resil"},
        headers=auth_header(user),
    )
    spy_arq.fail = True  # next enqueue_job raises

    r = await client.get("/resil", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "https://resilient.com/"
