"""
Data import endpoint — admin only.

Accepts CSV uploads and runs the full ETL pipeline per
Data Architecture Spec v0.3 Section 7.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_admin
from auth.entra import CurrentUser
from db.connection import get_db
from pipeline import PipelineHalt, run_import

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # 50 MB
ALLOWED_CONTENT_TYPES = {"text/csv", "application/vnd.ms-excel"}


@router.post("/")
async def upload_import(
    file: UploadFile,
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Content-type check
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted.",
        )

    # Size check — read one byte past the limit to detect oversize files
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 50 MB limit.",
        )

    filename = file.filename or "upload.csv"

    try:
        result = await run_import(
            csv_bytes=contents,
            source_filename=filename,
            imported_by=user.id,
            db=db,
        )
    except PipelineHalt as exc:
        # Hard-stop conditions: schema change, PII detected, key unavailable.
        # No data has been written — session rolls back when the dependency exits.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    await db.commit()

    return {
        "batch_id": str(result.batch_id),
        "total_records": result.total_records,
        "imported_records": result.imported_records,
        "skipped_records": result.skipped_records,
        "rejected_records": result.rejected_records,
        "rejection_log": [
            {"record_id": e.record_id, "reason": e.reason, "detail": e.detail}
            for e in result.rejection_log
        ],
    }


