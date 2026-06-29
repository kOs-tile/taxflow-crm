"""
TaxFlow CRM — Test Configuration
Shared fixtures using in-memory SQLite for fast, isolated tests.
"""
import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport

# Use in-memory database for tests
import os
os.environ["DATABASE_URL"] = ":memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ADMIN_EMAIL"] = "test@taxflow.app"
os.environ["ADMIN_PASSWORD"] = "TestPassword123!"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def app():
    from backend.main import app as fastapi_app
    from backend.db import init_db
    await init_db()
    return fastapi_app


@pytest_asyncio.fixture(scope="session")
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_headers(client):
    """Get auth headers for the default admin user."""
    res = await client.post("/api/auth/login", json={
        "email": "test@taxflow.app",
        "password": "TestPassword123!"
    })
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_client(client, auth_headers):
    """Create a sample client for testing."""
    res = await client.post(
        "/api/clients?auto_deadlines=false",
        json={
            "full_name": "Test Client",
            "email": f"testclient{id(object())}@test.com",
            "entity_type": "individual",
            "tax_year": 2024,
            "filing_status": "single",
            "state": "CA",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201
    return res.json()
