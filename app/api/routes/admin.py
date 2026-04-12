"""
Admin endpoints — admin role only.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_admin
from auth.entra import CurrentUser
from db.connection import get_db

router = APIRouter()


@router.get("/users")
async def list_users(user: CurrentUser = Depends(require_admin)):
    # User management is via Entra ID — this endpoint surfaces role assignments
    return {"message": "User management via Entra ID App Role assignments."}


@router.get("/audit-log")
async def get_audit_log(user: CurrentUser = Depends(require_admin)):
    # Audit log is in Log Analytics — surface via Azure Monitor query or direct log stream
    return {"message": "Audit log available via Azure Log Analytics workspace."}


@router.get("/batches")
async def list_batches(
    limit: Optional[int] = Query(default=None, ge=1, le=200),
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return import batch history, most recent first. Optional ?limit=N."""
    from sqlalchemy import select
    from db.models import ImportBatch

    q = select(ImportBatch).order_by(ImportBatch.imported_at.desc())
    if limit is not None:
        q = q.limit(limit)

    result = await db.execute(q)
    batches = result.scalars().all()
    return {
        "batches": [
            {
                "batch_id": str(b.batch_id),
                "imported_at": b.imported_at.isoformat(),
                "source_filename": b.source_filename,
                "total_records": b.total_records,
                "imported_records": b.imported_records,
                "skipped_records": b.skipped_records,
                "rejected_records": b.rejected_records,
                "notes": b.notes,
            }
            for b in batches
        ]
    }
