"""
Test configuration and shared fixtures.

Database strategy:
  Each test function gets a real PostgreSQL session wrapped in a transaction
  that is unconditionally rolled back at teardown. DB state never persists
  between tests. The schema is created once per session and dropped at the end.

Auth strategy:
  get_current_user is replaced once (session-scoped) with a ContextVar-based
  shim. Each role-specific client fixture wraps requests via _PerRequestUserTransport,
  which sets the ContextVar for the duration of each individual HTTP call.

  This means two clients (e.g. researcher_client + admin_client) can be active
  in the same test without trampling each other's user override — the ContextVar
  is resolved per-request, not per-fixture-setup.

  Tests that need to verify 401 responses use the anon_client fixture, which
  does NOT use _PerRequestUserTransport, so the ContextVar remains at its
  default (None) and the shim raises 401.

Pseudonymisation key:
  TEST_PSEUDONYMISATION_KEY env var provides a fixed, documented test key.
  This key is NEVER used in production. See Test Strategy v0.1 Section 3.1.
"""

import os
import urllib.parse
from contextvars import ContextVar
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport, Request as HttpxRequest, Response as HttpxResponse
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


# ── ContextVar-based user override ───────────────────────────────────────────
#
# The ContextVar is set for the duration of each HTTP request by
# _PerRequestUserTransport. Tests that require two roles simultaneously
# (e.g. test_list_returns_own_reports_only) each get the correct user because
# the ContextVar is set inside the transport's handle_async_request, which runs
# within the same coroutine as the ASGI call — so each client's requests see
# the user it was configured with.

_active_test_user: ContextVar[Optional[CurrentUser]] = ContextVar(
    "_active_test_user", default=None
)


async def _contextvar_get_current_user() -> CurrentUser:
    """Shim for get_current_user: reads the per-request ContextVar."""
    user = _active_test_user.get()
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


class _PerRequestUserTransport(ASGITransport):
    """
    httpx transport that sets _active_test_user for the lifetime of each request.
    Allows two clients with different users to coexist in the same test.
    """

    def __init__(self, user: CurrentUser):
        super().__init__(app=app)
        self._user = user

    async def handle_async_request(self, request: HttpxRequest) -> HttpxResponse:
        token = _active_test_user.set(self._user)
        try:
            return await super().handle_async_request(request)
        finally:
            _active_test_user.reset(token)


@pytest.fixture(autouse=True, scope="session")
def _install_user_override():
    """
    Replace get_current_user with the ContextVar shim once for the whole session.
    Individual client fixtures control which user is active via _PerRequestUserTransport.
    """
    app.dependency_overrides[get_current_user] = _contextvar_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


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
    Uses plain ASGITransport — _active_test_user stays at its default (None),
    so _contextvar_get_current_user raises 401 for any protected endpoint.
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
    try:
        async with AsyncClient(
            transport=_PerRequestUserTransport(user=viewer_user),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def viewer_client_no_db(viewer_user: CurrentUser) -> AsyncClient:
    """
    Authenticated viewer client with no DB dependency.
    Use for tests where the 403 role check fires before any DB access is needed.
    """
    async with AsyncClient(
        transport=_PerRequestUserTransport(user=viewer_user),
        base_url="http://test",
    ) as client:
        yield client


@pytest_asyncio.fixture
async def researcher_client(db_session: AsyncSession, researcher_user: CurrentUser) -> AsyncClient:
    """Authenticated client with researcher role."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=_PerRequestUserTransport(user=researcher_user),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession, admin_user: CurrentUser) -> AsyncClient:
    """Authenticated client with admin role."""
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(
            transport=_PerRequestUserTransport(user=admin_user),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Fixtures directory ────────────────────────────────────────────────────────

@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
