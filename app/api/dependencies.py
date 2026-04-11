"""
Shared FastAPI dependencies — auth and database.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.entra import CurrentUser
from db.connection import get_db


def get_current_user(request: Request) -> CurrentUser:
    user_data = request.session.get("user")
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    return CurrentUser(user_data)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    user.require_role("admin")
    return user


def require_researcher(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    user.require_role("admin", "researcher")
    return user
