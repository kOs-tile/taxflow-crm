"""
TaxFlow CRM — Test Configuration
Session-scoped fixtures with a single shared temp database.
"""
import os
import tempfile

# ── Step 1: Create a temp DB file ─────────────────────────────────────────────
_test_db = tempfile.NamedTemporaryFile(suffix=".test.db", delete=False)
_test_db.close()
TEST_DB_PATH = _test_db.name

# ── Step 2: Set ALL env vars BEFORE any backend import ────────────────────────
os.environ["DATABASE_URL"] = TEST_DB_PATH
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only-abc123"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ADMIN_EMAIL"] = "test@taxflow.app"
os.environ["ADMIN_PASSWORD"] = "TestPassword123!"

# ── Step 3: Clear settings cache BEFORE importing backend ─────────────────────
# This ensures get_settings() returns a fresh Settings() that reads our env vars.
from backend.config import get_settings
get_settings.cache_clear()

# ── Step 4: Now import backend modules (they will call get_settings() fresh) ──
import backend.db as db_module  # noqa: E402 — must come after cache_clear

# ── Step 5: Ensure DB_PATH module variable also points to test DB ──────────────
# (redundant now that _db_path() calls get_settings(), but kept for safety)
db_module.DB_PATH = TEST_DB_PATH

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def app():
    """Build FastAPI app with test DB, initialize schema + admin user."""
    # Re-clear cache in case another import sneaked in
    get_settings.cache_clear()

    from backend.main import app as fastapi_app
    from backend.db import init_db

    # Ensure db module still points at test path (defensive)
    db_module.DB_PATH = TEST_DB_PATH

    await init_db()
    yield fastapi_app


@pytest_asyncio.fixture(scope="session")
async def client(app):
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_headers(client):
    """Get auth headers for the default admin user (reused across all tests)."""
    res = await client.post("/api/auth/login", json={
        "email": "test@taxflow.app",
        "password": "TestPassword123!"
    })
    assert res.status_code == 200, f"Login failed: {res.status_code} {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_client(client, auth_headers):
    """Create a fresh client for each test that needs one."""
    import time
    unique_email = f"testclient{int(time.time()*1000000)}@test.com"
    res = await client.post(
        "/api/clients?auto_deadlines=false",
        json={
            "full_name": "Test Client",
            "email": unique_email,
            "entity_type": "individual",
            "tax_year": 2024,
            "filing_status": "single",
            "state": "CA",
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, f"Create client failed: {res.text}"
    return res.json()
