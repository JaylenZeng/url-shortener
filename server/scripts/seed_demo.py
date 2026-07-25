"""Seed a demo account with realistic data to show off the app in a demo.

Creates (or resets) a single demo user, a handful of short links that read like
a real developer's collection, and a month of click events spread across those
links with believable referrers, user agents, and traffic shapes (a viral
launch spike, steady evergreen links, a slow-burn grower, and some sparse ones).
That's enough to make every screen — the link list, per-link analytics, the
clicks-by-day chart, top referrers, and top user agents — look alive.

The script talks to the database directly (it does not go through the HTTP API),
so it skips email-deliverability checks and rate limits.

Usage
-----
Run from the ``server/`` directory. By default it targets ``DATABASE_URL``
(from the environment or ``.env``); pass ``--database-url`` to point it
elsewhere — e.g. the ``shortener`` database the Docker stack uses::

    # local dev DB (whatever DATABASE_URL / .env resolves to)
    uv run python scripts/seed_demo.py

    # the running Docker stack's database
    uv run python scripts/seed_demo.py \\
        --database-url postgresql+asyncpg://postgres:postgres@localhost:5432/shortener

    uv run python scripts/seed_demo.py --keep     # error out if demo user exists
    uv run python scripts/seed_demo.py --days 60  # widen the analytics window

The schema must already exist (``alembic upgrade head`` or a running stack).

It is safe to re-run: by default it wipes the demo user's existing links and
click events first, so you always get a clean, deterministic dataset (the RNG
is seeded), and you never pile up duplicates.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Allow `python scripts/seed_demo.py` from the server/ dir without installing.
sys.path.insert(0, ".")

from app.core.config import settings  # noqa: E402
from app.models import ClickEvent, Link, User  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# Demo credentials — advertise these on the login screen during a demo.
# ---------------------------------------------------------------------------
DEMO_EMAIL = "demo@short.link"
DEMO_PASSWORD = "demodemo123"

# Deterministic output so every demo looks the same.
random.seed(42)

# ---------------------------------------------------------------------------
# The links. `total` is a rough target click count; `shape` controls how those
# clicks are spread across the analytics window.
#   viral   — a big spike a few days after launch, with a decaying tail
#   growing — slow start, accelerating toward today
#   steady  — even traffic with day-to-day noise
#   sparse  — a trickle of clicks
# ---------------------------------------------------------------------------
LINKS = [
    dict(alias="launch", url="https://www.producthunt.com/posts/shortlink",
         total=780, shape="viral", days_ago_created=34),
    dict(alias="gh", url="https://github.com/jaylenzeng/url-shortener",
         total=420, shape="steady", days_ago_created=45),
    dict(alias="blog", url="https://jaylen.dev/blog/scaling-a-url-shortener",
         total=360, shape="growing", days_ago_created=40),
    dict(alias="resume", url="https://jaylen.dev/resume.pdf",
         total=95, shape="steady", days_ago_created=50),
    dict(alias="talk", url="https://slides.com/jaylen/redis-click-pipeline",
         total=210, shape="viral", days_ago_created=20),
    dict(alias="docs", url="https://docs.short.link/getting-started",
         total=140, shape="growing", days_ago_created=38),
    dict(alias="newsletter", url="https://jaylen.substack.com/subscribe",
         total=88, shape="steady", days_ago_created=33),
    dict(alias=None, url="https://arxiv.org/abs/2401.01234",
         total=24, shape="sparse", days_ago_created=42),
    dict(alias="sale", url="https://shop.example.com/black-friday",
         total=160, shape="viral", days_ago_created=12,
         expires_in_days=7),
    dict(alias="webinar", url="https://zoom.us/webinar/register/abc123",
         total=12, shape="sparse", days_ago_created=6,
         expires_in_days=3),
]

# (referrer, weight). None = direct visit / no referrer header.
REFERRERS = [
    ("https://news.ycombinator.com/", 20),
    ("https://twitter.com/", 16),
    ("https://www.google.com/", 15),
    ("https://www.linkedin.com/feed/", 12),
    ("https://www.reddit.com/r/programming/", 10),
    ("https://t.co/", 8),
    ("https://jaylen.substack.com/", 6),
    (None, 25),
]

# (user_agent, weight).
USER_AGENTS = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", 28),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36", 24),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
     "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 "
     "Safari/604.1", 18),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36", 12),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) "
     "Gecko/20100101 Firefox/127.0", 8),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0", 7),
    ("Mozilla/5.0 (compatible; Googlebot/2.1; "
     "+http://www.google.com/bot.html)", 3),
]


def _weighted(pairs: list[tuple]) -> object:
    values = [v for v, _ in pairs]
    weights = [w for _, w in pairs]
    return random.choices(values, weights=weights, k=1)[0]


def _random_ip() -> str:
    # Public-looking IPv4, avoiding reserved/private-ish first octets.
    return f"{random.randint(11, 223)}.{random.randint(0, 255)}." \
           f"{random.randint(0, 255)}.{random.randint(1, 254)}"


def _day_offsets(total: int, window_days: int, shape: str) -> list[int]:
    """Return `total` day-indices in [0, window_days-1] following `shape`.

    Index 0 is the oldest day in the window; window_days-1 is today.
    """
    offsets: list[int] = []
    for _ in range(total):
        if shape == "viral":
            # Spike a few days into the window, decaying tail afterwards.
            peak = window_days * 0.25
            idx = int(random.gauss(peak, window_days * 0.12))
        elif shape == "growing":
            # Bias toward recent days (sqrt pushes mass to the high end).
            idx = int((window_days - 1) * (random.random() ** 0.5))
        elif shape == "sparse":
            idx = random.randint(0, window_days - 1)
        else:  # steady
            idx = int(random.gauss((window_days - 1) / 2, window_days * 0.3))
        offsets.append(max(0, min(window_days - 1, idx)))
    return offsets


async def _reset(session, user: User) -> None:
    """Delete the demo user's existing links and click events."""
    link_ids = (
        await session.execute(select(Link.id).where(Link.user_id == user.id))
    ).scalars().all()
    if link_ids:
        await session.execute(
            delete(ClickEvent).where(ClickEvent.link_id.in_(link_ids))
        )
        await session.execute(delete(Link).where(Link.user_id == user.id))
    await session.flush()


async def seed(window_days: int, keep: bool, database_url: str) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    engine = create_async_engine(database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as session:
        user = await session.scalar(
            select(User).where(User.email == DEMO_EMAIL)
        )

        if user is not None:
            if keep:
                raise SystemExit(
                    f"Demo user {DEMO_EMAIL!r} already exists. "
                    "Re-run without --keep to reset it."
                )
            await _reset(session, user)
        else:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                created_at=now - timedelta(days=60),
            )
            session.add(user)
            await session.flush()

        total_clicks = 0
        for spec in LINKS:
            created_at = now - timedelta(days=spec["days_ago_created"])
            expires_at = None
            if "expires_in_days" in spec:
                expires_at = now + timedelta(days=spec["expires_in_days"])

            link = Link(
                short_code=spec["alias"] or _unique_code(),
                original_url=spec["url"],
                user_id=user.id,
                created_at=created_at,
                expires_at=expires_at,
            )
            session.add(link)
            await session.flush()  # assign link.id

            # A link can't be clicked before it existed: clip the window to
            # the link's lifetime so timestamps stay consistent.
            link_start = max(window_start, created_at)
            effective_days = max(1, (now - link_start).days)

            for idx in _day_offsets(spec["total"], effective_days, spec["shape"]):
                ts = link_start + timedelta(
                    days=idx,
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59),
                )
                if ts > now:
                    ts = now - timedelta(minutes=random.randint(1, 120))
                session.add(
                    ClickEvent(
                        link_id=link.id,
                        event_id=uuid.uuid4(),
                        timestamp=ts,
                        referrer=_weighted(REFERRERS),
                        user_agent=_weighted(USER_AGENTS),
                        ip=_random_ip(),
                    )
                )
                total_clicks += 1

        await session.commit()

    await engine.dispose()

    print("\n✅ Demo account seeded.\n")
    print(f"   Email:    {DEMO_EMAIL}")
    print(f"   Password: {DEMO_PASSWORD}")
    print(f"   Links:    {len(LINKS)}")
    print(f"   Clicks:   {total_clicks} over ~{window_days} days\n")
    print("   Log in with the above credentials to explore the dashboard.\n")


# Generated codes for links without a custom alias. Kept short and readable.
_used_codes: set[str] = set()


def _unique_code(length: int = 7) -> str:
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        if code not in _used_codes:
            _used_codes.add(code)
            return code


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=30,
        help="Size of the analytics window in days (default: 30).",
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="Fail instead of resetting if the demo user already exists.",
    )
    parser.add_argument(
        "--database-url", default=settings.database_url,
        help="Async SQLAlchemy DB URL to seed (default: DATABASE_URL / .env).",
    )
    args = parser.parse_args()
    print(f"Seeding {args.database_url.rsplit('@', 1)[-1]} …")
    asyncio.run(
        seed(window_days=args.days, keep=args.keep,
             database_url=args.database_url)
    )


if __name__ == "__main__":
    main()
