"""
Integration tests for the auth routes: register, login, and the
get_current_user dependency guarding an authenticated endpoint.
"""
import dns.exception
import dns.resolver
import pytest
from httpx import AsyncClient

from app.core.config import settings
from app.services import auth_service
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


# ---- register ---------------------------------------------------------------

async def test_register_success(client: AsyncClient):
    r = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"
    assert "id" in body
    assert "password_hash" not in body  # UserResponse must not leak the hash


async def test_register_duplicate_email_conflicts(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "password123"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_register_rejects_short_password(client: AsyncClient):
    r = await client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "short"},
    )
    assert r.status_code == 422  # Pydantic min_length


async def test_register_rejects_bad_email(client: AsyncClient):
    r = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert r.status_code == 422


# ---- email deliverability (MX) check ----------------------------------------

async def test_register_rejects_undeliverable_domain(client: AsyncClient, monkeypatch):
    """A syntactically valid email whose domain can't receive mail → 422."""
    monkeypatch.setattr(settings, "verify_email_deliverability", True)

    async def _reject(email: str) -> bool:
        return False

    monkeypatch.setattr("app.routes.auth.email_domain_accepts_mail", _reject)
    r = await client.post(
        "/auth/register",
        json={"email": "someone@totally-made-up-xyz.com", "password": "password123"},
    )
    assert r.status_code == 422
    assert "domain" in r.json()["error"].lower()


async def test_register_allows_deliverable_domain(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "verify_email_deliverability", True)

    async def _accept(email: str) -> bool:
        return True

    monkeypatch.setattr("app.routes.auth.email_domain_accepts_mail", _accept)
    r = await client.post(
        "/auth/register",
        json={"email": "real@example.com", "password": "password123"},
    )
    assert r.status_code == 201


# ---- email_domain_accepts_mail unit tests -----------------------------------

class _FakeAnswer:
    def __init__(self, exchange):
        self.exchange = exchange


def _fake_resolver(monkeypatch, behavior):
    """Patch the async DNS resolver. `behavior` maps a record type to either a
    list of answers, or an Exception instance to raise for that lookup."""
    class _FakeResolver:
        def __init__(self):
            self.timeout = None
            self.lifetime = None

        async def resolve(self, domain, rdtype):
            result = behavior.get(rdtype, dns.resolver.NoAnswer())
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(
        auth_service.dns.asyncresolver, "Resolver", lambda: _FakeResolver()
    )


async def test_domain_with_mx_is_deliverable(monkeypatch):
    _fake_resolver(monkeypatch, {"MX": [_FakeAnswer("mail.example.com.")]})
    assert await auth_service.email_domain_accepts_mail("a@example.com") is True


async def test_null_mx_is_not_deliverable(monkeypatch):
    # RFC 7505 null MX: a single "." target = explicitly accepts no mail.
    _fake_resolver(monkeypatch, {"MX": [_FakeAnswer(".")]})
    assert await auth_service.email_domain_accepts_mail("a@no-mail.example") is False


async def test_no_mx_falls_back_to_a_record(monkeypatch):
    _fake_resolver(monkeypatch, {"MX": dns.resolver.NoAnswer(), "A": ["1.2.3.4"]})
    assert await auth_service.email_domain_accepts_mail("a@example.com") is True


async def test_no_mail_records_is_not_deliverable(monkeypatch):
    _fake_resolver(
        monkeypatch,
        {
            "MX": dns.resolver.NoAnswer(),
            "A": dns.resolver.NoAnswer(),
            "AAAA": dns.resolver.NoAnswer(),
        },
    )
    assert await auth_service.email_domain_accepts_mail("a@example.com") is False


async def test_nonexistent_domain_is_not_deliverable(monkeypatch):
    _fake_resolver(monkeypatch, {"MX": dns.resolver.NXDOMAIN()})
    assert await auth_service.email_domain_accepts_mail("a@nope.invalid") is False


async def test_dns_timeout_fails_open(monkeypatch):
    # Infrastructure failure must not block legitimate signups.
    _fake_resolver(monkeypatch, {"MX": dns.exception.Timeout()})
    assert await auth_service.email_domain_accepts_mail("a@example.com") is True


# ---- login ------------------------------------------------------------------

async def test_login_success_returns_token(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "password123"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_401(client: AsyncClient):
    await client.post(
        "/auth/register",
        json={"email": "login2@example.com", "password": "password123"},
    )
    r = await client.post(
        "/auth/login",
        json={"email": "login2@example.com", "password": "wrongpassword"},
    )
    assert r.status_code == 401


async def test_login_unknown_email_401(client: AsyncClient):
    r = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert r.status_code == 401


# ---- auth dependency --------------------------------------------------------

async def test_protected_route_requires_token(client: AsyncClient):
    r = await client.get("/links")  # no Authorization header
    assert r.status_code == 401


async def test_protected_route_rejects_garbage_token(client: AsyncClient):
    r = await client.get("/links", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


async def test_protected_route_accepts_valid_token(client: AsyncClient, user):
    r = await client.get("/links", headers=auth_header(user))
    assert r.status_code == 200
