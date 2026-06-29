"""
TaxFlow CRM — Auth Tests
Tests: staff login, token validation, protected routes.
"""
import pytest


@pytest.mark.asyncio
class TestStaffAuth:

    async def test_successful_login(self, client):
        """Admin can log in with correct credentials."""
        res = await client.post(
            "/api/auth/login",
            json={"email": "test@taxflow.app", "password": "TestPassword123!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "test@taxflow.app"
        assert data["user"]["role"] == "admin"

    async def test_wrong_password_rejected(self, client):
        """Login fails with wrong password."""
        res = await client.post(
            "/api/auth/login",
            json={"email": "test@taxflow.app", "password": "WrongPassword!"},
        )
        assert res.status_code == 401

    async def test_unknown_email_rejected(self, client):
        """Login fails with unknown email."""
        res = await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "anything"},
        )
        assert res.status_code == 401

    async def test_token_used_for_protected_route(self, client, auth_headers):
        """Valid token allows access to protected routes."""
        res = await client.get("/api/clients", headers=auth_headers)
        assert res.status_code == 200

    async def test_no_token_rejected(self, client):
        """No token → 401."""
        res = await client.get("/api/clients")
        assert res.status_code == 401

    async def test_invalid_token_rejected(self, client):
        """Malformed token → 401."""
        res = await client.get(
            "/api/clients",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert res.status_code == 401

    async def test_health_endpoint_is_public(self, client):
        """Health check is publicly accessible."""
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"

    async def test_token_refresh(self, client, auth_headers):
        """Token refresh returns new token."""
        res = await client.post("/api/auth/refresh", headers=auth_headers)
        assert res.status_code == 200
        assert "access_token" in res.json()
