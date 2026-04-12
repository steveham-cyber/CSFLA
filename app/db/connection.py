"""
PostgreSQL connection using Azure Managed Identity.

In Azure:    No password. An Entra ID access token is fetched fresh for each
             connection via DefaultAzureCredential (Managed Identity).
             Tokens expire after ~1 hour — using NullPool ensures a fresh token
             is acquired for every request rather than reusing stale connections.
             The DB user must be an Entra ID user with CONNECT privilege.

Local dev:   DB_PASSWORD is set in .env and used directly. A connection pool
             is used for efficiency.
"""
from __future__ import annotations

import urllib.parse
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from config import get_settings

settings = get_settings()


async def _get_azure_token_password() -> str:
    """Fetch a fresh Entra ID access token to use as the PostgreSQL password."""
    from azure.identity.aio import DefaultAzureCredential
    credential = DefaultAzureCredential()
    token = await credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    await credential.close()
    return token.token


@lru_cache
def _get_local_engine() -> AsyncEngine:
    """Cached engine for local development — password from .env."""
    password = urllib.parse.quote_plus(settings.db_password)
    url = (
        f"postgresql+asyncpg://{settings.db_user}:{password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )
    return create_async_engine(url, echo=False, pool_size=5)


async def _create_azure_engine() -> AsyncEngine:
    """
    Create a short-lived engine with a fresh Managed Identity token.

    NullPool is used intentionally — Azure AD tokens expire after ~1 hour and
    cannot be injected into existing pooled connections. Creating a new engine
    per request (with NullPool) ensures the token is always current.
    For a high-traffic deployment, replace this with a pool event listener that
    refreshes the token before the pool_recycle interval.
    """
    token = await _get_azure_token_password()
    url = (
        f"postgresql+asyncpg://{settings.db_user}:{urllib.parse.quote_plus(token)}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        "?ssl=require"
    )
    return create_async_engine(url, echo=False, poolclass=NullPool)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency — yields a database session.

    Local:      Uses the cached local engine (connection pool).
    Production: Creates a fresh engine per request with a new Managed Identity
                token (NullPool — see _create_azure_engine for rationale).
    """
    if settings.is_local:
        engine = _get_local_engine()
        dispose_after = False
    else:
        engine = await _create_azure_engine()
        dispose_after = True

    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    if dispose_after:
        await engine.dispose()
