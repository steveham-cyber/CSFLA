"""
Custom report endpoints — CRUD and query execution.

Reports are user-scoped by Entra ID OID.
All mutations use POST (CORS allows GET/POST only).

Security:
  - OID-scoped access: _get_own_report() enforces id AND created_by match
  - QueryDefinition validates all field keys against VALID_FIELD_KEYS allowlist
  - name max 100 chars, description max 500 chars (Pydantic)
  - /fields and /run registered before /{report_id} to prevent path-param shadowing
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
from reports.query_builder import VALID_FIELD_KEYS, get_fields, run_query

log = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic models ───────────────────────────────────────────────────────────

class QueryDefinition(BaseModel):
    """Validated report definition: which fields to group by and filter on."""

    dimensions: list[str] = Field(..., min_length=1, max_length=6)
    filters: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, v: list[str]) -> list[str]:
        invalid = [d for d in v if d not in VALID_FIELD_KEYS]
        if invalid:
            raise ValueError(f"Unknown dimension fields: {invalid}")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate dimensions are not allowed")
        return v

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict) -> dict:
        invalid = [k for k in v if k not in VALID_FIELD_KEYS]
        if invalid:
            raise ValueError(f"Unknown filter fields: {invalid}")
        for key, values in v.items():
            if not values:
                raise ValueError(
                    f"Filter values for {key!r} must not be empty"
                )
        return v


class CreateReportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    definition: QueryDefinition


class UpdateReportRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    definition: Optional[QueryDefinition] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_report_id(report_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(report_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report not found.")


async def _get_own_report(
    report_uuid: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession,
) -> CustomReport:
    """
    Fetch a report and assert it belongs to this user.
    Returns 404 for both missing reports and reports owned by other users
    (no information leakage about existence).
    """
    result = await db.execute(
        select(CustomReport).where(
            CustomReport.id == report_uuid,
            CustomReport.created_by == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


async def _audit(
    db: AsyncSession,
    report_id: uuid.UUID | None,
    action: str,
    performed_by: str,
    detail: dict | None = None,
) -> None:
    db.add(
        CustomReportAudit(
            report_id=report_id,
            action=action,
            performed_by=performed_by,
            performed_at=datetime.now(timezone.utc),
            detail=detail,
        )
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────
# NOTE: /fields and /run MUST be registered before /{report_id} so FastAPI
# does not treat the literal strings "fields" and "run" as path parameters.

@router.get("/fields")
async def list_fields(
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Return all available fields with labels and allowed values."""
    return {"fields": await get_fields(db)}


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
                "dimension_count": len(r.definition.get("dimensions", [])),
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
        detail={"name": report.name},
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


@router.post("/run")
async def run_unsaved_report(
    body: QueryDefinition,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Execute a query definition without saving it."""
    return await run_query(db, body.dimensions, body.filters)


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
    report = await _get_own_report(_parse_report_id(report_id), user, db)
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
async def run_saved_report(
    report_id: str,
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Execute a saved report and write an audit row."""
    report = await _get_own_report(_parse_report_id(report_id), user, db)
    defn = report.definition
    result = await run_query(db, defn["dimensions"], defn.get("filters", {}))
    await _audit(
        db,
        report_id=report.id,
        action="run",
        performed_by=user.id,
        detail={"dimension_count": len(defn["dimensions"])},
    )
    await db.commit()
    return {"report_id": str(report.id), "name": report.name, **result}


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
