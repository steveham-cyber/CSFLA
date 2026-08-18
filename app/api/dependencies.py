"""
Shared FastAPI dependencies — auth and database.
"""

import asyncio
import logging
import time

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.entra import CurrentUser, get_msal_app, SCOPES
from db.connection import get_db

log = logging.getLogger(__name__)

_REVALIDATION_INTERVAL_SECONDS = 300  # 5 minutes


async def get_current_user(request: Request) -> CurrentUser:
    user_data = request.session.get("user")
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    now = time.time()
    last_validated = request.session.get("roles_validated_at", 0.0)

    if now - last_validated > _REVALIDATION_INTERVAL_SECONDS:
        home_account_id = request.session.get("home_account_id")
        if not home_account_id:
            # Legacy session predating this change — force re-auth
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )

        msal_app = get_msal_app()
        accounts = await asyncio.to_thread(msal_app.get_accounts)
        account = next(
            (a for a in accounts if a["home_account_id"] == home_account_id),
            None,
        )

        if account is None:
            # Not in MSAL cache (worker restart, new instance) — force re-auth
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Please log in again.",
            )

        result = await asyncio.to_thread(
            msal_app.acquire_token_silent, SCOPES, account=account
        )

        if not result or "error" in result:
            log.warning(
                "MSAL silent token acquisition failed for account %s: %s",
                home_account_id,
                result.get("error") if result else "no result",
            )
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication could not be verified. Please log in again.",
            )

        # Refresh roles from fresh claims if available
        fresh_claims = result.get("id_token_claims")
        if fresh_claims and "roles" in fresh_claims:
            user_data = {**user_data, "roles": fresh_claims["roles"]}
            request.session["user"] = user_data

        request.session["roles_validated_at"] = now

    return CurrentUser(user_data)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    user.require_role("admin")
    return user


def require_researcher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Standard reports — accessible to viewer, researcher, and admin."""
    user.require_role("admin", "researcher", "viewer")
    return user


def require_researcher_no_viewer(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Custom report builder — viewer excluded per Lex compliance ruling."""
    user.require_role("admin", "researcher")
    return user
