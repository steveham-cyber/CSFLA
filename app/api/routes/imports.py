"""
Data import endpoint — admin only.
Pipeline implementation locked pending Cipher + Lex sign-off (ACTIONS.md A-07, A-10).
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from api.dependencies import require_admin
from auth.entra import CurrentUser

router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_CONTENT_TYPES = {"text/csv", "application/vnd.ms-excel"}


@router.post("/")
async def upload_import(
    file: UploadFile,
    user: CurrentUser = Depends(require_admin),
):
    # File type validation
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are accepted.",
        )

    # File size validation
    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 50MB limit.",
        )

    # Pipeline is not yet implemented — locked pending sign-off
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Import pipeline pending compliance sign-off.",
    )


@router.get("/batches")
async def list_batches(user: CurrentUser = Depends(require_admin)):
    # Stub — returns import batch history
    return {"batches": []}
