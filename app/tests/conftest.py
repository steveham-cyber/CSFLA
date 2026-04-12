"""
Test configuration and shared fixtures.

Database strategy:
  Each test function gets a real PostgreSQL session wrapped in a transaction
  that is unconditionally rolled back at teardown. DB state never persists
  between tests. The schema is created once per session and dropped at the end.

Auth strategy:
  get_current_user is overridden via app.dependency_overrides for each
  role-specific client fixture. Tests that need to verify 401 responses
  use the anon_client fixture (no override — dependency runs normally).

Pseudonymisation key:
  TEST_PSEUDONYMISATION_KEY env var provides a fixed, documented test key.
  This key is NEVER used in production. See Test Strategy v0.1 Section 3.1.
"""

import os
import urllib.parse
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from main import app
from db.connection import get_db
from db.models import Base
from api.dependencies import get_current_user
from auth.entra import CurrentUser


# ── Test key ─────────────────────────────────────────────────────────────────

#: Fixed test key — used by all pseudonymisation tests.
#: Never equal to any production key value (enforced by CI: this string
#: is the fixed test value, the production key lives in Azure Key Vault).
TEST_PSEUDONYMISATION_KEY: str = os.environ.get(
    "TEST_PSEUDONYMISATION_KEY",
    "test-hmac-key-csfleak-never-use-in-production-aabbccdd",
)

# Ensure key_vault.get_pseudonymisation_key() finds the key in dev mode.
# setdefault does nothing if the var is already set (e.g. from CI secrets).
os.environ.setdefault("TEST_PSEUDONYMISATION_KEY", TEST_PSEUDONYMISATION_KEY)


# ── Test database URL ─────────────────────────────────────────────────────────

def _test_db_url() -> str:
    user = os.environ.get("DB_USER", "test")
    password = urllib.parse.quote_plus(os.environ.get("DB_PASSWORD", "test"))
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "csfleak_test")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    """
    Session-scoped engine — creates the full schema once, drops it at the end.
    Never touches production or staging databases.
    """
    engine = create_async_engine(_test_db_url(), echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncSession:
    """
    Function-scoped session. Each test runs inside a transaction that is rolled
    back unconditionally at teardown — DB state never persists between tests.
    """
    async with test_engine.connect() as connection:
        await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await connection.rollback()


# ── User fixtures ─────────────────────────────────────────────────────────────

def _make_user(role: str) -> CurrentUser:
    """Build a CurrentUser with a single role, using a synthetic Entra ID OID."""
    return CurrentUser({
        "oid": f"00000000-0000-0000-0000-{role[:12].ljust(12, '0')}",
        "name": f"Test {role.capitalize()} User",
        "roles": [role],
    })


@pytest.fixture
def viewer_user() -> CurrentUser:
    return _make_user("viewer")


@pytest.fixture
def researcher_user() -> CurrentUser:
    return _make_user("researcher")


@pytest.fixture
def admin_user() -> CurrentUser:
    return _make_user("admin")


# ── HTTP client fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def anon_client() -> AsyncClient:
    """
    Unauthenticated HTTP client.
    get_current_user is NOT overridden — requests will receive 401 from the
    real dependency if no session is present.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def viewer_client(db_session: AsyncSession, viewer_user: CurrentUser) -> AsyncClient:
    """Authenticated client with viewer role."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def researcher_client(db_session: AsyncSession, researcher_user: CurrentUser) -> AsyncClient:
    """Authenticated client with researcher role."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: researcher_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession, admin_user: CurrentUser) -> AsyncClient:
    """Authenticated client with admin role."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


# ── Fixtures directory ────────────────────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
