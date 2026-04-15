"""
Custom report endpoints — CRUD and execution.

All endpoints require researcher role (admin/researcher/viewer).
Reports are user-scoped: each user can only access their own reports (by Entra ID OID).

Uses POST for mutations (create, update, delete, run) to stay within the
existing CORS allow_methods=["GET","POST"] configuration.

Cipher security requirements implemented here:
- OID-scoped access control on every read/update/delete/run endpoint
- definition.blocks[].report_id validated against allowed set r1-r8
- definition.blocks[].filters keys allowlisted via VALID_FILTER_KEYS
- instance_id sanitised (bounded alphanumeric string)
- Maximum 8 blocks per report enforced
- name (max 100 chars) and description (max 500 chars) enforced via Pydantic
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_researcher
from auth.entra import CurrentUser
from db.connection import get_db
from db.models import CustomReport, CustomReportAudit
from reports.blocks import BLOCKS, VALID_FILTER_KEYS, run_block

log = logging.getLogger(__name__)

router = APIRouter()

MAX_BLOCKS_PER_REPORT = 8
MAX_NAME_LENGTH = 100


# ── Request / response models ─────────────────────────────────────────────────

class BlockDefinition(BaseModel):
    instance_id: str = Field(..., min_length=1, max_length=32, pattern=r'^[a-zA-Z0-9_-]+$')
    report_id: str
    title: Optional[str] = Field(default=None, max_length=100)
    filters: dict[str, Optional[str | int]] = Field(default_factory=dict)

    @field_validator('report_id')
    @classmethod
    def validate_report_id(cls, v: str) -> str:
        if v not in BLOCKS:
            raise ValueError(f"Unknown report block: {v!r}")
        return v

    @field_validator('filters')
    @classmethod
    def validate_filter_keys(cls, v: dict) -> dict:
        unknown = set(v.keys()) - VALID_FILTER_KEYS
        if unknown:
            raise ValueError(f"Unknown filter keys: {unknown}")
        return v


class ReportDefinition(BaseModel):
    blocks: list[BlockDefinition] = Field(..., min_length=1)

    @field_validator('blocks')
    @classmethod
    def validate_blocks(cls, v: list[BlockDefinition]) -> list[BlockDefinition]:
        if len(v) > MAX_BLOCKS_PER_REPORT:
            raise ValueError(f"Maximum {MAX_BLOCKS_PER_REPORT} blocks per report")
        ids = [b.instance_id for b in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Block instance_ids must be unique within a report")
        return v


class CreateReportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_NAME_LENGTH)
    description: Optional[str] = Field(default=None, max_length=500)
    definition: ReportDefinition


class UpdateReportRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=MAX_NAME_LENGTH)
    description: Optional[str] = Field(default=None, max_length=500)
    definition: Optional[ReportDefinition] = None


class PreviewRequest(BaseModel):
    definition: ReportDefinition


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_report_id(report_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")


async def _get_own_report(
    report_uuid: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession,
) -> CustomReport:
    """Fetch a report and assert it belongs to this user. Raises 404 otherwise."""
    result = await db.execute(
        select(CustomReport).where(
            CustomReport.id == report_uuid,
            CustomReport.created_by == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return report


async def _audit(
    db: AsyncSession,
    report_id: uuid.UUID | None,
    action: str,
    performed_by: str,
    detail: dict | None = None,
) -> None:
    entry = CustomReportAudit(
        report_id=report_id,
        action=action,
        performed_by=performed_by,
        performed_at=datetime.now(timezone.utc),
        detail=detail,
    )
    db.add(entry)


# ── Endpoints ─────────────────────────────────────────────────────────────────
# NOTE: /blocks and /preview are registered BEFORE /{report_id} to prevent
# FastAPI treating the literal strings "blocks" and "preview" as path parameters.

@router.get("/blocks")
async def list_blocks(user: CurrentUser = Depends(require_researcher)):
    """Return the catalogue of available report blocks."""
    return {
        "blocks": [
            {
                "id": block_id,
                "title": block["title"],
                "description": block["description"],
                "filters": block["filters"],
            }
            for block_id, block in BLOCKS.items()
        ]
    }


@router.get("/")
async def list_custom_reports(
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """List the current user's saved custom reports."""
    result = await db.execute(
        select(CustomReport)
        .where(CustomReport.created_by == user.id)
        .order_by(CustomReport.updated_at.desc())
    )
    reports = result.scalars().all()
    return {
        "reports": [
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description,
                "block_count": len(r.definition.get("blocks", [])),
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in reports
        ]
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_custom_report(
    body: CreateReportRequest,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Create and persist a new custom report."""
    report = CustomReport(
        created_by=user.id,
        name=body.name,
        description=body.description,
        definition=body.definition.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.flush()
    await _audit(
        db,
        report_id=report.id,
        action="create",
        performed_by=user.id,
        detail={"name": report.name, "block_count": len(body.definition.blocks)},
    )
    await db.commit()
    await db.refresh(report)
    return {
        "id": str(report.id),
        "name": report.name,
        "description": report.description,
        "definition": report.definition,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


@router.post("/preview")
async def preview_custom_report(
    body: PreviewRequest,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Execute a report definition without saving. Used for live preview in the builder."""
    definition = body.definition.model_dump()
    results = await _execute_definition(db, definition)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blocks": results,
    }


@router.get("/{report_id}")
async def get_custom_report(
    report_id: str,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Get a single custom report definition. Returns 404 if not owned by user."""
    report = await _get_own_report(_parse_report_id(report_id), user, db)
    return {
        "id": str(report.id),
        "name": report.name,
        "description": report.description,
        "definition": report.definition,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


@router.post("/{report_id}/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_report(
    report_id: str,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom report. Returns 404 if not owned by user."""
    report_uuid = _parse_report_id(report_id)
    report = await _get_own_report(report_uuid, user, db)

    await _audit(
        db,
        report_id=None,
        action="delete",
        performed_by=user.id,
        detail={"deleted_id": str(report.id), "name": report.name},
    )
    await db.delete(report)
    await db.commit()


@router.post("/{report_id}/run")
async def run_custom_report(
    report_id: str,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Execute all blocks in a saved report and return results keyed by instance_id."""
    report = await _get_own_report(_parse_report_id(report_id), user, db)
    results = await _execute_definition(db, report.definition)
    await _audit(
        db,
        report_id=report.id,
        action="run",
        performed_by=user.id,
        detail={"block_count": len(report.definition.get("blocks", []))},
    )
    await db.commit()
    return {
        "report_id": str(report.id),
        "name": report.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "blocks": results,
    }


@router.post("/{report_id}")
async def update_custom_report(
    report_id: str,
    body: UpdateReportRequest,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Update name, description, or definition of an existing report."""
    report = await _get_own_report(_parse_report_id(report_id), user, db)

    if body.name is not None:
        report.name = body.name
    if body.description is not None:
        report.description = body.description
    if body.definition is not None:
        report.definition = body.definition.model_dump()
    report.updated_at = datetime.now(timezone.utc)

    await _audit(
        db,
        report_id=report.id,
        action="update",
        performed_by=user.id,
        detail={"name": report.name},
    )
    await db.commit()
    await db.refresh(report)
    return {
        "id": str(report.id),
        "name": report.name,
        "description": report.description,
        "definition": report.definition,
        "updated_at": report.updated_at.isoformat(),
    }


async def _execute_definition(db: AsyncSession, definition: dict) -> dict:
    """
    Run all blocks in a definition dict. Returns a dict keyed by instance_id.
    Each value is {"ok": True, "data": {...}} or {"ok": False, "error": "..."}.
    """
    results: dict[str, dict] = {}
    for block in definition.get("blocks", []):
        instance_id = block["instance_id"]
        try:
            data = await run_block(db, block["report_id"], block.get("filters", {}))
            results[instance_id] = {"ok": True, "data": data}
        except Exception as exc:
            log.error("Block %r execution failed: %s", block.get("report_id"), exc)
            results[instance_id] = {"ok": False, "error": "Block execution failed."}
    return results
