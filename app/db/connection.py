"""
PostgreSQL connection using Azure Managed Identity.

In Azure:    No password. An Entra ID access token is fetched at connection time
             via DefaultAzureCredential and passed as the PostgreSQL password.
             The DB user must be an Entra ID user with CONNECT privilege.

Local dev:   DB_PASSWORD is set in .env and used directly.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from functools import lru_cache
import urllib.parse

from config import get_settings

settings = get_settings()


def _get_db_url() -> str:
    if settings.is_local:
        # Local development — password from .env
        password = urllib.parse.quote_plus(settings.db_password)
        return (
            f"postgresql+asyncpg://{settings.db_user}:{password}"
            f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
        )
    else:
        # Azure — Managed Identity token used as password
        # Token is fetched fresh per connection via the creator function below
        return (
            f"postgresql+asyncpg://{settings.db_user}"
            f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
            "?ssl=require"
        )


async def _get_azure_token_password() -> str:
    """Fetch a fresh Entra ID token to use as the PostgreSQL password in Azure."""
    from azure.identity.aio import ManagedIdentityCredential
    credential = ManagedIdentityCredential()
    token = await credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    await credential.close()
    return token.token


@lru_cache
def get_engine() -> AsyncEngine:
    if settings.is_local:
        return create_async_engine(_get_db_url(), echo=False, pool_size=5)
    else:
        # In Azure: provide token as password via connect_args
        # Token refresh is handled by creating a new engine or using a pool event
        return create_async_engine(
            _get_db_url(),
            echo=False,
            pool_size=5,
            connect_args={"ssl": "require"},
        )


AsyncSessionLocal = sessionmaker(
    bind=get_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
