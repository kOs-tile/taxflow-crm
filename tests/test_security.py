"""SEC-20261103-01: auth and cross-origin regression checks."""

import pytest
from fastapi import HTTPException

from backend.auth import create_access_token, decode_token, hash_password, verify_password
from backend.config import get_settings


def test_password_hash_uses_bcrypt_and_rejects_wrong_password():
    encrypted = hash_password("some-long-safe-password")
    assert encrypted.startswith(("$2a$", "$2b$", "$2y$"))
    assert verify_password("some-long-safe-password", encrypted)
    assert not verify_password("incorrect", encrypted)


def test_legacy_sha256_password_hash_is_not_accepted():
    # Production data must be migrated through an audited credential reset.
    assert not verify_password("password", "sha256:legacy-salt:legacy-digest")


def test_jwt_roundtrip_and_signature_validation():
    token = create_access_token({"sub": "1", "type": "staff"})
    assert decode_token(token)["sub"] == "1"
    with pytest.raises(HTTPException) as exc:
        decode_token(token + "tampered")
    assert exc.value.status_code == 401


def test_auth_algorithm_is_pinned_to_hs256():
    assert get_settings().jwt_algorithm == "HS256"


@pytest.mark.asyncio
async def test_trusted_browser_origin_preflight(client):
    response = await client.options(
        "/api/clients",
        headers={
            "Origin": "https://app.example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://app.example.test"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_untrusted_browser_origin_cannot_use_cors(client):
    response = await client.options(
        "/api/clients",
        headers={
            "Origin": "https://untrusted.example.test",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
