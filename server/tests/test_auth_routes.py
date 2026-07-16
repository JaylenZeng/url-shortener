"""
Integration tests for the auth routes: register, login, and the
get_current_user dependency guarding an authenticated endpoint.
"""
import pytest
from httpx import AsyncClient

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
