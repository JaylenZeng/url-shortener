"""
Pure unit tests — no database, no HTTP. Fast, deterministic.
Covers: short-code generation, password hashing, JWT creation/decoding.
"""
import uuid

import pytest
from jose import jwt

from app.config import settings
from app.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.services.link_service import generate_code, ALPHABET


# ---- generate_code ----------------------------------------------------------

def test_generate_code_default_length():
    assert len(generate_code()) == 7


def test_generate_code_custom_length():
    assert len(generate_code(12)) == 12


def test_generate_code_uses_alphabet():
    code = generate_code(50)
    assert all(ch in ALPHABET for ch in code)


def test_generate_code_is_random():
    # Two calls should (essentially always) differ. Collision here is ~1 in 62^7.
    assert generate_code() != generate_code()


# ---- password hashing -------------------------------------------------------

def test_hash_is_not_plaintext():
    hashed = hash_password("password123")
    assert hashed != "password123"


def test_hash_is_salted_unique():
    # Same password, two hashes -> different, because the salt is random.
    assert hash_password("password123") != hash_password("password123")


def test_verify_correct_password():
    hashed = hash_password("password123")
    assert verify_password("password123", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("password123")
    assert verify_password("wrongpassword", hashed) is False


# ---- JWT --------------------------------------------------------------------

def test_token_roundtrip_carries_subject():
    uid = str(uuid.uuid4())
    token = create_access_token(uid)
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert payload["sub"] == uid


def test_token_has_expiry():
    token = create_access_token(str(uuid.uuid4()))
    payload = jwt.decode(
        token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert "exp" in payload


def test_token_rejects_wrong_secret():
    token = create_access_token(str(uuid.uuid4()))
    with pytest.raises(jwt.JWTError):
        jwt.decode(token, "not-the-secret", algorithms=[settings.jwt_algorithm])
