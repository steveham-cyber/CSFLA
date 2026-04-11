"""
Admin endpoints — admin role only.
"""

from fastapi import APIRouter, Depends

from api.dependencies import require_admin
from auth.entra import CurrentUser

router = APIRouter()


@router.get("/users")
async def list_users(user: CurrentUser = Depends(require_admin)):
    # User management is via Entra ID — this endpoint surfaces role assignments
    return {"message": "User management via Entra ID App Role assignments."}


@router.get("/audit-log")
async def get_audit_log(user: CurrentUser = Depends(require_admin)):
    # Audit log is in Log Analytics — surface via Azure Monitor query or direct log stream
    return {"message": "Audit log available via Azure Log Analytics workspace."}
