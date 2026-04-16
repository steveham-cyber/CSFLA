# Custom Report Builder Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing block-composition custom report builder with a flat-table query builder where researchers pick GROUP BY fields, apply per-field filters, and see member counts.

**Architecture:** A new `app/reports/query_builder.py` module owns all dynamic SQL logic (field catalogue, JOIN selection, suppression). A rewritten `app/api/routes/custom_reports.py` exposes GET /fields, POST /run, and CRUD endpoints. The template and JS are replaced wholesale; the `custom_reports` and `custom_report_audit` DB tables stay unchanged.

**Tech Stack:** FastAPI, SQLAlchemy async (raw `text()` queries), Pydantic v2, Jinja2, vanilla JS (no framework, no SortableJS), PostgreSQL. Test runner: pytest-asyncio with `asyncio_mode = auto`.

---

## File Map

| Action | Path |
|---|---|
| Create | `app/reports/query_builder.py` |
| Replace | `app/api/routes/custom_reports.py` |
| Create | `app/db/migrations/truncate_custom_reports.sql` |
| Replace | `app/templates/report_builder.html` |
| Replace | `app/static/js/report_builder.js` |
| Modify | `app/api/routes/ui.py` — fix `active_nav` bug on builder routes |
| Delete | `app/reports/blocks.py` |
| Replace | `app/tests/test_api/test_custom_reports.py` |

---

## Task 1: Query Builder Module

**Files:**
- Create: `app/reports/query_builder.py`
- Test: `app/tests/test_api/test_custom_reports.py` (pure unit tests, no DB)

- [ ] **Step 1: Write the failing unit tests**

Replace `app/tests/test_api/test_custom_reports.py` with:

```python
"""
Custom report tests — query builder unit tests + API tests.
DB-dependent tests require the test PostgreSQL instance (csfleak_test).
Tests without a db_session fixture run without a DB connection.
"""
import pytest


class TestQueryBuilderUnit:
    """Pure unit tests — no DB needed."""

    def test_valid_field_keys(self) -> None:
        from reports.query_builder import VALID_FIELD_KEYS
        assert VALID_FIELD_KEYS == {
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        }

    def test_field_order(self) -> None:
        from reports.query_builder import FIELD_ORDER
        assert FIELD_ORDER == [
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        ]

    def test_cause_group_col_expr_uses_col_alias(self) -> None:
        from reports.query_builder import _CAUSE_GROUP_COL_EXPR
        assert "col.cause" in _CAUSE_GROUP_COL_EXPR
        assert "CASE" in _CAUSE_GROUP_COL_EXPR

    def test_cause_group_col_expr_covers_all_groups(self) -> None:
        from reports.query_builder import _CAUSE_GROUP_COL_EXPR
        for group in ("Iatrogenic", "Connective Tissue Disorder",
                      "Spontaneous / Structural", "Traumatic"):
            assert group in _CAUSE_GROUP_COL_EXPR

    def test_available_fields_has_six_entries(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        assert len(AVAILABLE_FIELDS) == 6

    def test_leak_type_has_four_enum_values(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        assert set(AVAILABLE_FIELDS["leak_type"]["values"]) == {
            "spinal", "cranial", "spinalAndCranial", "unknown",
        }

    def test_dynamic_fields_have_no_values_list(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        for key in ("country", "gender", "age_band"):
            assert AVAILABLE_FIELDS[key]["dynamic"] is True
            assert "values" not in AVAILABLE_FIELDS[key]

    def test_enum_fields_have_values_list(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        for key in ("leak_type", "cause_group", "individual_cause"):
            assert AVAILABLE_FIELDS[key]["dynamic"] is False
            assert isinstance(AVAILABLE_FIELDS[key]["values"], list)
            assert len(AVAILABLE_FIELDS[key]["values"]) > 0
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest tests/test_api/test_custom_reports.py::TestQueryBuilderUnit -v
```

Expected: `ModuleNotFoundError: No module named 'reports.query_builder'`

- [ ] **Step 3: Create `app/reports/query_builder.py`**

```python
"""
Custom report query builder.

Builds and executes dynamic GROUP BY queries from a report definition.
Enforces k>=10 cohort suppression unconditionally on every query.

Field sources:
  members table         → country, gender, age_band          (alias m)
  csf_leak_types table  → leak_type                          (alias clt)
  causes_of_leak table  → cause_group, individual_cause      (alias col)
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from reports import (
    MIN_COHORT_SIZE,
    CAUSE_GROUPS,
    CAUSE_GROUP_ORDER,
    CAUSE_TO_GROUP,
)

# CASE WHEN expression mapping col.cause values to group names.
# Uses alias 'col' for causes_of_leak (the shared CAUSE_GROUP_CASE_EXPR
# in reports/__init__.py uses alias 'c' — this one uses 'col').
_CAUSE_GROUP_COL_EXPR: str = (
    "CASE "
    + " ".join(
        "WHEN col.cause IN ({}) THEN '{}'".format(
            ", ".join(f"'{v}'" for v in sorted(causes)),
            group,
        )
        for group, causes in CAUSE_GROUPS.items()
    )
    + " ELSE 'Unknown / Not disclosed' END"
)

# ── Field catalogue ───────────────────────────────────────────────────────

FIELD_ORDER: list[str] = [
    "country",
    "gender",
    "age_band",
    "leak_type",
    "cause_group",
    "individual_cause",
]

AVAILABLE_FIELDS: dict[str, dict] = {
    "country": {
        "label": "Country",
        "source": "members",
        "col_expr": "m.country",
        "dynamic": True,
    },
    "gender": {
        "label": "Gender",
        "source": "members",
        "col_expr": "m.gender",
        "dynamic": True,
    },
    "age_band": {
        "label": "Age Band",
        "source": "members",
        "col_expr": "m.age_band",
        "dynamic": True,
    },
    "leak_type": {
        "label": "CSF Leak Type",
        "source": "csf_leak_types",
        "col_expr": "clt.leak_type",
        "dynamic": False,
        "values": ["spinal", "cranial", "spinalAndCranial", "unknown"],
    },
    "cause_group": {
        "label": "Cause Group",
        "source": "causes_of_leak",
        "col_expr": _CAUSE_GROUP_COL_EXPR,
        "dynamic": False,
        "values": list(CAUSE_GROUP_ORDER),
    },
    "individual_cause": {
        "label": "Individual Cause",
        "source": "causes_of_leak",
        "col_expr": "col.cause",
        "dynamic": False,
        "values": sorted(CAUSE_TO_GROUP.keys()),
    },
}

VALID_FIELD_KEYS: frozenset[str] = frozenset(AVAILABLE_FIELDS.keys())


# ── Public API ────────────────────────────────────────────────────────────

async def get_fields(db: AsyncSession) -> list[dict]:
    """
    Return all available fields with labels and allowed values.
    Dynamic fields (country, gender, age_band) query DISTINCT from DB.
    Enum fields return hardcoded controlled vocabularies.
    """
    result = []
    for key in FIELD_ORDER:
        field = AVAILABLE_FIELDS[key]
        if field["dynamic"]:
            col = field["col_expr"]
            rows = (
                await db.execute(
                    text(
                        f"SELECT DISTINCT {col} FROM members m"
                        f" WHERE {col} IS NOT NULL ORDER BY {col}"
                    )
                )
            ).scalars().all()
            values = list(rows)
        else:
            values = field["values"]
        result.append({"key": key, "label": field["label"], "values": values})
    return result


async def run_query(
    db: AsyncSession,
    dimensions: list[str],
    filters: dict[str, list[str]],
) -> dict:
    """
    Execute a GROUP BY query for the given dimensions and filters.

    Returns:
        {
            "columns": [...],
            "rows": [{"dim1": v, ..., "member_count": n}, ...],
            "total_shown": int,
            "suppressed_count": int,
        }

    k<10 combinations are excluded from rows and counted in suppressed_count.
    COUNT(DISTINCT m.pseudo_id) is used throughout to avoid double-counting
    when joining one-to-many tables.
    """
    all_fields = set(dimensions) | set(filters.keys())

    needs_leak = any(
        AVAILABLE_FIELDS[f]["source"] == "csf_leak_types" for f in all_fields
    )
    needs_cause = any(
        AVAILABLE_FIELDS[f]["source"] == "causes_of_leak" for f in all_fields
    )

    # ── SELECT and GROUP BY expressions ──────────────────────────────────
    select_exprs: list[str] = []
    group_exprs: list[str] = []

    for dim in dimensions:
        col = AVAILABLE_FIELDS[dim]["col_expr"]
        select_exprs.append(f"{col} AS {dim}")
        group_exprs.append(col)

    select_exprs.append("COUNT(DISTINCT m.pseudo_id) AS member_count")

    # ── FROM + JOINs ──────────────────────────────────────────────────────
    from_parts = ["FROM members m"]
    if needs_leak:
        from_parts.append(
            "LEFT JOIN csf_leak_types clt ON clt.pseudo_id = m.pseudo_id"
        )
    if needs_cause:
        from_parts.append(
            "LEFT JOIN causes_of_leak col ON col.pseudo_id = m.pseudo_id"
        )
    from_sql = "\n        ".join(from_parts)

    # ── WHERE conditions ──────────────────────────────────────────────────
    conditions: list[str] = []
    params: dict = {"min_cohort": MIN_COHORT_SIZE}

    for field_key, values in filters.items():
        if not values:
            continue

        if field_key == "cause_group":
            # Translate group names → individual cause values for WHERE clause.
            # (The CASE WHEN expression is only in SELECT/GROUP BY.)
            individual_causes = [
                cause
                for cause, grp in CAUSE_TO_GROUP.items()
                if grp in values
            ]
            if individual_causes:
                pnames = [f"fg_{i}" for i in range(len(individual_causes))]
                placeholders = ", ".join(f":{p}" for p in pnames)
                conditions.append(f"col.cause IN ({placeholders})")
                for pname, val in zip(pnames, individual_causes):
                    params[pname] = val
        else:
            col_expr = AVAILABLE_FIELDS[field_key]["col_expr"]
            pnames = [f"f_{field_key}_{i}" for i in range(len(values))]
            placeholders = ", ".join(f":{p}" for p in pnames)
            conditions.append(f"{col_expr} IN ({placeholders})")
            for pname, val in zip(pnames, values):
                params[pname] = val

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    group_sql = ("GROUP BY " + ", ".join(group_exprs)) if group_exprs else ""
    order_sql = ("ORDER BY " + ", ".join(group_exprs)) if group_exprs else ""

    # ── Main query ────────────────────────────────────────────────────────
    main_q = f"""
        SELECT {", ".join(select_exprs)}
        {from_sql}
        {where_sql}
        {group_sql}
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_cohort
        {order_sql}
    """

    # ── Suppressed count query ────────────────────────────────────────────
    suppressed_q = f"""
        SELECT COUNT(*) FROM (
            SELECT COUNT(DISTINCT m.pseudo_id) AS n
            {from_sql}
            {where_sql}
            {group_sql}
            HAVING COUNT(DISTINCT m.pseudo_id) < :min_cohort
        ) suppressed
    """

    rows = (await db.execute(text(main_q), params)).fetchall()
    suppressed_count: int = (
        await db.execute(text(suppressed_q), params)
    ).scalar() or 0

    result_rows = []
    for row in rows:
        row_dict = {dim: row[i] for i, dim in enumerate(dimensions)}
        row_dict["member_count"] = row[len(dimensions)]
        result_rows.append(row_dict)

    return {
        "columns": dimensions,
        "rows": result_rows,
        "total_shown": sum(r["member_count"] for r in result_rows),
        "suppressed_count": suppressed_count,
    }
```

- [ ] **Step 4: Run unit tests — expect PASS**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest tests/test_api/test_custom_reports.py::TestQueryBuilderUnit -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
cd app
git add reports/query_builder.py tests/test_api/test_custom_reports.py
git commit -m "feat: add query_builder module with field catalogue and run_query"
```

---

## Task 2: New API Routes

**Files:**
- Replace: `app/api/routes/custom_reports.py`
- Test: `app/tests/test_api/test_custom_reports.py` (append new classes — no DB)

- [ ] **Step 1: Add API auth + validation tests (append to existing test file)**

Add these classes to `app/tests/test_api/test_custom_reports.py` — append after `TestQueryBuilderUnit`:

```python
class TestCustomReportAuth:
    """Auth enforcement — no DB needed."""

    async def test_fields_requires_auth(self, anon_client) -> None:
        response = await anon_client.get("/api/custom-reports/fields")
        assert response.status_code == 401

    async def test_list_requires_auth(self, anon_client) -> None:
        response = await anon_client.get("/api/custom-reports/")
        assert response.status_code == 401

    async def test_run_requires_auth(self, anon_client) -> None:
        response = await anon_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 401

    async def test_create_requires_auth(self, anon_client) -> None:
        response = await anon_client.post(
            "/api/custom-reports/",
            json={"name": "x", "definition": {"dimensions": ["country"]}},
        )
        assert response.status_code == 401


class TestQueryDefinitionValidation:
    """Pydantic validation — no DB needed (422 returned before DB is touched)."""

    async def test_run_empty_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run", json={"dimensions": []}
        )
        assert response.status_code == 422

    async def test_run_unknown_dimension_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run", json={"dimensions": ["nonexistent_field"]}
        )
        assert response.status_code == 422

    async def test_run_duplicate_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country", "country"]},
        )
        assert response.status_code == 422

    async def test_run_seven_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        # Only 6 fields exist; any list longer than 6 is invalid
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": [
                    "country", "gender", "age_band",
                    "leak_type", "cause_group", "individual_cause",
                    "country",   # 7th = duplicate triggers duplicate error
                ]
            },
        )
        assert response.status_code == 422

    async def test_run_unknown_filter_field_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"], "filters": {"bogus": ["val"]}},
        )
        assert response.status_code == 422

    async def test_run_empty_filter_values_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"], "filters": {"gender": []}},
        )
        assert response.status_code == 422

    async def test_create_empty_name_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "", "definition": {"dimensions": ["country"]}},
        )
        assert response.status_code == 422
```

- [ ] **Step 2: Run new tests — expect FAIL (routes not yet replaced)**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest \
  tests/test_api/test_custom_reports.py::TestCustomReportAuth \
  tests/test_api/test_custom_reports.py::TestQueryDefinitionValidation -v
```

Expected: failures because the existing routes still use the old `ReportDefinition` model (and `/fields` and `/run` don't exist yet).

- [ ] **Step 3: Replace `app/api/routes/custom_reports.py`**

```python
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
```

- [ ] **Step 4: Run auth + validation tests — expect PASS**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest \
  tests/test_api/test_custom_reports.py::TestCustomReportAuth \
  tests/test_api/test_custom_reports.py::TestQueryDefinitionValidation -v
```

Expected: all 11 tests pass (no DB required for these).

- [ ] **Step 5: Commit**

```bash
git add api/routes/custom_reports.py tests/test_api/test_custom_reports.py
git commit -m "feat: replace custom report API with query builder endpoints"
```

---

## Task 3: Migration Script

**Files:**
- Create: `app/db/migrations/truncate_custom_reports.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- Migration: truncate custom reports tables
-- Reason: old block-composition definition format is incompatible with the
--         new query-builder format. Run once before deploying the new builder.
--
-- Run with:
--   psql $DATABASE_URL -f app/db/migrations/truncate_custom_reports.sql

TRUNCATE TABLE custom_report_audit;
TRUNCATE TABLE custom_reports;
```

- [ ] **Step 2: Run the migration against your local dev DB**

```bash
# From the project root — adjust DATABASE_URL to your local connection string
psql postgresql://localhost/csfleak -f app/db/migrations/truncate_custom_reports.sql
```

Expected output:
```
TRUNCATE TABLE
TRUNCATE TABLE
```

- [ ] **Step 3: Commit**

```bash
git add db/migrations/truncate_custom_reports.sql
git commit -m "chore: add migration to truncate old block-based custom reports"
```

---

## Task 4: Template and UI Route Fix

**Files:**
- Replace: `app/templates/report_builder.html`
- Modify: `app/api/routes/ui.py` (fix `active_nav` bug on builder routes)
- Test: `app/tests/test_api/test_custom_reports.py` (append `TestUIRoutes`)

- [ ] **Step 1: Add UI route tests (append to test file)**

```python
class TestUIRoutes:
    """Builder pages require auth — no DB needed."""

    async def test_builder_redirects_unauthenticated(
        self, anon_client
    ) -> None:
        response = await anon_client.get("/reports/builder")
        # UI routes redirect (302) rather than returning 401
        assert response.status_code == 302

    async def test_builder_new_redirects_unauthenticated(
        self, anon_client
    ) -> None:
        response = await anon_client.get("/reports/builder/new")
        assert response.status_code == 302

    async def test_builder_accessible_to_researcher(
        self, researcher_client
    ) -> None:
        response = await researcher_client.get("/reports/builder")
        assert response.status_code == 200
```

- [ ] **Step 2: Run UI route tests — expect PASS (routes already exist)**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest \
  tests/test_api/test_custom_reports.py::TestUIRoutes -v
```

Expected: `3 passed`

- [ ] **Step 3: Fix `active_nav` bug in `app/api/routes/ui.py`**

In `ui.py`, find the three builder route handlers (lines 87–129). Each currently passes `"active_nav": "reports"`. Change all three to `"active_nav": "builder"`:

```python
# report_builder_list (line ~96)
"active_nav": "builder",

# report_builder_new (line ~112)
"active_nav": "builder",

# report_builder_edit (line ~122)
"active_nav": "builder",
```

- [ ] **Step 4: Replace `app/templates/report_builder.html`**

```html
{% extends "base.html" %}

{% block title %}Custom Reports — CSFLA Research{% endblock %}

{% block extra_head %}
<script src="/static/js/report_builder.js" defer></script>
{% endblock %}

{% block content %}
<div id="builder-root"
     data-report-id="{{ report_id or '' }}"
     style="display:flex;flex-direction:column;height:100%;overflow:hidden;">

  <!-- ── Page header ──────────────────────────────────────────────────── -->
  <div style="
    background:var(--color-bg-white);
    border-bottom:1px solid var(--color-border);
    padding:var(--space-3) var(--space-6);
    display:flex;align-items:center;justify-content:space-between;
    gap:var(--space-3);flex-shrink:0;
  ">
    <h1 style="
      font-size:var(--font-size-lg);
      letter-spacing:var(--letter-spacing-title);
      color:var(--color-primary);
      white-space:nowrap;
    ">Custom Reports</h1>

    <div style="display:flex;align-items:center;gap:var(--space-2);flex:1;justify-content:flex-end;">
      <input id="report-name-input" type="text" placeholder="Report name…"
        maxlength="100" autocomplete="off"
        style="
          border:1px solid var(--color-border);
          border-radius:var(--radius-md);
          padding:6px var(--space-3);
          font-size:var(--font-size-sm);
          font-family:inherit;
          color:var(--color-primary);
          width:220px;
        "/>
      <button id="btn-new" style="
        background:var(--color-bg-white);color:var(--color-primary);
        border:1px solid var(--color-border);border-radius:var(--radius-md);
        padding:6px var(--space-3);font-size:var(--font-size-sm);
        font-weight:var(--font-weight-medium);cursor:pointer;font-family:inherit;
      ">New</button>
      <button id="btn-save" style="
        background:var(--color-primary-mid);color:#fff;border:none;
        border-radius:var(--radius-md);padding:6px var(--space-3);
        font-size:var(--font-size-sm);font-weight:var(--font-weight-bold);
        cursor:pointer;font-family:inherit;
      ">Save</button>
      <button id="btn-run" style="
        background:var(--color-primary);color:#fff;border:none;
        border-radius:var(--radius-md);padding:6px var(--space-3);
        font-size:var(--font-size-sm);font-weight:var(--font-weight-bold);
        cursor:pointer;font-family:inherit;
      ">&#9654; Run</button>
    </div>
  </div>

  <!-- ── Saved reports bar ────────────────────────────────────────────── -->
  <div id="saved-bar" style="
    background:var(--color-bg-card);
    border-bottom:1px solid var(--color-border);
    padding:var(--space-2) var(--space-6);
    display:flex;align-items:center;gap:var(--space-2);
    overflow-x:auto;min-height:40px;flex-shrink:0;
  ">
    <span style="
      font-size:var(--font-size-xs);color:var(--color-text-muted);
      white-space:nowrap;font-weight:var(--font-weight-medium);
    ">Saved:</span>
  </div>

  <!-- ── Builder body ─────────────────────────────────────────────────── -->
  <div style="display:flex;flex:1;overflow:hidden;min-height:0;">

    <!-- Left panel: dimensions + filters -->
    <div id="left-panel" style="
      width:280px;flex-shrink:0;
      background:var(--color-bg-white);
      border-right:1px solid var(--color-border);
      overflow-y:auto;padding:var(--space-4);
    "></div>

    <!-- Right panel: results table -->
    <div id="right-panel" style="flex:1;overflow-y:auto;padding:var(--space-5) var(--space-6);">
      <div id="result-area">
        <div style="text-align:center;padding:64px var(--space-6);color:var(--color-text-muted);">
          <div style="font-size:32px;margin-bottom:var(--space-3);">&#8862;</div>
          <p style="font-size:var(--font-size-sm);">Select fields and press Run</p>
        </div>
      </div>
    </div>

  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Verify the builder page loads without error**

Start the dev server and visit `http://localhost:8000/reports/builder` (after auth). The page should load with the header, saved bar, empty left panel, and empty right panel. The browser console should show fetch errors for `/api/custom-reports/fields` and `/api/custom-reports/` (JS not yet written — that's Task 5).

- [ ] **Step 6: Commit**

```bash
cd app
git add templates/report_builder.html api/routes/ui.py \
  tests/test_api/test_custom_reports.py
git commit -m "feat: replace report_builder template; fix active_nav on builder routes"
```

---

## Task 5: Builder JavaScript

**Files:**
- Replace: `app/static/js/report_builder.js`

- [ ] **Step 1: Replace `app/static/js/report_builder.js`**

```javascript
'use strict';

// ── State ─────────────────────────────────────────────────────────────────────

const S = {
    reportId:     null,   // UUID string or null
    reportName:   '',
    dimensions:   [],     // ordered array of field keys
    filters:      {},     // { fieldKey: [value, ...] }
    catalogue:    [],     // [{ key, label, values }] from GET /fields
    savedReports: [],     // [{ id, name, ... }] from GET /
};

// ── DOM refs ──────────────────────────────────────────────────────────────────

const ROOT       = document.getElementById('builder-root');
const nameInput  = document.getElementById('report-name-input');
const savedBar   = document.getElementById('saved-bar');
const leftPanel  = document.getElementById('left-panel');
const resultArea = document.getElementById('result-area');

// ── Security helper ───────────────────────────────────────────────────────────

function _esc(s) {
    return String(s)
        .replace(/&/g,  '&amp;')
        .replace(/</g,  '&lt;')
        .replace(/>/g,  '&gt;')
        .replace(/"/g,  '&quot;')
        .replace(/'/g,  '&#39;');
}

// ── Catalogue helpers ─────────────────────────────────────────────────────────

function fieldMeta(key) {
    return S.catalogue.find(f => f.key === key) || { key, label: key, values: [] };
}

const ORDINALS = ['1st', '2nd', '3rd', '4th', '5th', '6th'];

// ── Render: left panel ────────────────────────────────────────────────────────

function renderLeft() {
    const dimIndex = Object.fromEntries(S.dimensions.map((k, i) => [k, i]));

    // ── Dimensions section ────────────────────────────────────────────────────
    let html = '<div style="margin-bottom:var(--space-5)">';
    html += '<div style="font-size:11px;font-weight:700;color:var(--color-text-muted);'
          + 'text-transform:uppercase;letter-spacing:1px;margin-bottom:var(--space-2)">Group By</div>';

    for (const field of S.catalogue) {
        const isActive = field.key in dimIndex;
        const isIndividualCause = field.key === 'individual_cause';
        const ordinal = isActive ? ORDINALS[dimIndex[field.key]] : null;
        html += `<div class="dim-pill" data-field="${_esc(field.key)}" style="
            display:flex;align-items:center;justify-content:space-between;
            padding:8px 10px;border-radius:var(--radius-md);
            border:1.5px solid ${isActive ? 'var(--color-primary)' : 'var(--color-border)'};
            margin-bottom:6px;cursor:pointer;
            font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);
            color:${isActive ? '#fff' : 'var(--color-primary)'};
            background:${isActive ? 'var(--color-primary)' : 'var(--color-bg-white)'};
            opacity:${!isActive && isIndividualCause ? '0.65' : '1'};
        ">
            <span>${_esc(field.label)}</span>
            ${isActive
                ? `<span style="font-size:11px;font-weight:700;background:rgba(255,255,255,0.25);
                     color:#fff;border-radius:99px;padding:1px 7px;">${ordinal}</span>`
                : `<span style="font-size:11px;color:var(--color-text-muted)">+ add</span>`
            }
        </div>`;
    }
    html += '</div>';

    // ── Filters section ───────────────────────────────────────────────────────
    // Show a filter block for every active dimension AND every filter-only field.
    const filterFields = [...new Set([...S.dimensions, ...Object.keys(S.filters)])];

    html += '<div>';
    html += '<div style="font-size:11px;font-weight:700;color:var(--color-text-muted);'
          + 'text-transform:uppercase;letter-spacing:1px;margin-bottom:var(--space-2)">Filters</div>';

    for (const key of filterFields) {
        const field    = fieldMeta(key);
        const isFilterOnly = !S.dimensions.includes(key);
        const active   = S.filters[key] || [];
        const available = field.values.filter(v => !active.includes(v));

        html += `<div style="margin-bottom:var(--space-3)">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                <span style="font-size:12px;font-weight:var(--font-weight-medium);color:var(--color-primary)">
                    ${_esc(field.label)}
                </span>
                ${isFilterOnly
                    ? `<button class="remove-filter-field" data-field="${_esc(key)}"
                         style="background:none;border:none;cursor:pointer;
                                color:var(--color-text-muted);font-size:16px;line-height:1;padding:0;">×</button>`
                    : ''}
            </div>`;

        if (available.length > 0) {
            html += `<select class="filter-add-select" data-field="${_esc(key)}"
                style="width:100%;border:1px solid var(--color-border);
                       border-radius:var(--radius-md);padding:6px var(--space-2);
                       font-size:12px;font-family:inherit;
                       background:var(--color-bg-card);color:var(--color-text-body);">
                <option value="">Add value…</option>`;
            for (const v of available) {
                html += `<option value="${_esc(v)}">${_esc(v)}</option>`;
            }
            html += `</select>`;
        }

        if (active.length > 0) {
            html += `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:5px;">`;
            for (const v of active) {
                html += `<span style="background:var(--color-bg-shape);color:var(--color-primary);
                    font-size:11px;font-weight:var(--font-weight-medium);border-radius:99px;
                    padding:2px 8px;display:inline-flex;align-items:center;gap:4px;">
                    ${_esc(v)}
                    <button class="remove-filter-val"
                        data-field="${_esc(key)}" data-value="${_esc(v)}"
                        style="background:none;border:none;cursor:pointer;
                               color:var(--color-text-muted);font-size:13px;line-height:1;padding:0;">×</button>
                </span>`;
            }
            html += `</div>`;
        }
        html += `</div>`;
    }

    // "Filter on another field" select — only fields not already in filterFields
    const nonFilterFields = S.catalogue.filter(f => !filterFields.includes(f.key));
    if (nonFilterFields.length > 0) {
        html += `<select id="add-filter-field"
            style="width:100%;border:1px solid var(--color-border);
                   border-radius:var(--radius-md);padding:6px var(--space-2);
                   font-size:12px;font-family:inherit;
                   background:var(--color-bg-white);color:var(--color-text-muted);
                   margin-top:var(--space-2);">
            <option value="">Filter on another field…</option>`;
        for (const f of nonFilterFields) {
            html += `<option value="${_esc(f.key)}">${_esc(f.label)}</option>`;
        }
        html += `</select>`;
    }

    html += '</div>';
    leftPanel.innerHTML = html;
    _attachLeftEvents();
}

function _attachLeftEvents() {
    // Dimension pill toggle
    leftPanel.querySelectorAll('.dim-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const key = pill.dataset.field;
            if (S.dimensions.includes(key)) {
                S.dimensions = S.dimensions.filter(k => k !== key);
            } else if (S.dimensions.length < 6) {
                S.dimensions.push(key);
            }
            renderLeft();
        });
    });

    // Filter value add
    leftPanel.querySelectorAll('.filter-add-select').forEach(sel => {
        sel.addEventListener('change', () => {
            const key = sel.dataset.field;
            const val = sel.value;
            if (!val) return;
            if (!S.filters[key]) S.filters[key] = [];
            if (!S.filters[key].includes(val)) S.filters[key].push(val);
            renderLeft();
        });
    });

    // Filter value remove
    leftPanel.querySelectorAll('.remove-filter-val').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            const key = btn.dataset.field;
            const val = btn.dataset.value;
            S.filters[key] = (S.filters[key] || []).filter(v => v !== val);
            if (S.filters[key].length === 0) delete S.filters[key];
            renderLeft();
        });
    });

    // Remove filter-only field
    leftPanel.querySelectorAll('.remove-filter-field').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            delete S.filters[btn.dataset.field];
            renderLeft();
        });
    });

    // Add filter-only field
    const addSel = document.getElementById('add-filter-field');
    if (addSel) {
        addSel.addEventListener('change', () => {
            const key = addSel.value;
            if (!key) return;
            if (!S.filters[key]) S.filters[key] = [];
            renderLeft();
        });
    }
}

// ── Render: saved bar ─────────────────────────────────────────────────────────

function renderSavedBar() {
    // Remove old chips (keep the "Saved:" label span)
    savedBar.querySelectorAll('button.saved-chip').forEach(c => c.remove());

    for (const r of S.savedReports) {
        const chip = document.createElement('button');
        chip.className = 'saved-chip';
        chip.textContent = r.name;
        chip.dataset.id  = r.id;
        const isActive = r.id === S.reportId;
        chip.style.cssText = `
            background:${isActive ? 'var(--color-primary)' : 'var(--color-bg-white)'};
            color:${isActive ? '#fff' : 'var(--color-primary)'};
            border:1px solid ${isActive ? 'var(--color-primary)' : 'var(--color-border)'};
            border-radius:99px;padding:3px 12px;font-size:12px;
            font-family:inherit;font-weight:var(--font-weight-medium);
            cursor:pointer;white-space:nowrap;
        `;
        chip.addEventListener('click', () => loadReport(r.id));
        savedBar.appendChild(chip);
    }
}

// ── Render: results ───────────────────────────────────────────────────────────

function renderEmptyResult() {
    resultArea.innerHTML = `
        <div style="text-align:center;padding:64px var(--space-6);color:var(--color-text-muted);">
            <div style="font-size:32px;margin-bottom:var(--space-3);">&#8862;</div>
            <p style="font-size:var(--font-size-sm);">Select fields and press Run</p>
        </div>`;
}

function renderResult(result) {
    let html = `
        <div style="display:flex;align-items:center;justify-content:space-between;
                    margin-bottom:var(--space-3);">
            <span style="font-size:var(--font-size-sm);font-weight:var(--font-weight-bold);
                         color:var(--color-primary);">Results</span>
            <span style="font-size:var(--font-size-xs);color:var(--color-text-muted);">
                ${result.total_shown.toLocaleString()} members shown
            </span>
        </div>`;

    if (result.suppressed_count > 0) {
        const n = result.suppressed_count;
        html += `
            <div style="background:#FFF8E8;border:1px solid var(--color-warning);
                        border-radius:var(--radius-md);padding:10px var(--space-4);
                        font-size:var(--font-size-xs);color:var(--color-text-body);
                        margin-bottom:var(--space-3);display:flex;
                        align-items:flex-start;gap:var(--space-2);">
                <span>&#9888;</span>
                <span><strong>${n} combination${n === 1 ? '' : 's'} hidden</strong>
                    — fewer than 10 members each. These are not shown to protect member privacy.</span>
            </div>`;
    }

    if (result.rows.length === 0) {
        html += `
            <div style="text-align:center;padding:var(--space-7) var(--space-6);
                        color:var(--color-text-muted);">
                <p style="font-size:var(--font-size-sm);">
                    No combinations with 10 or more members match the current filters.
                </p>
            </div>`;
    } else {
        html += `<div style="background:var(--color-bg-white);border:1px solid var(--color-border);
                              border-radius:var(--radius-md);overflow:hidden;
                              box-shadow:var(--shadow-card);">
            <table style="width:100%;border-collapse:collapse;">
                <thead><tr style="background:var(--color-bg-card);">`;

        for (const col of result.columns) {
            html += `<th style="padding:10px var(--space-4);font-size:11px;font-weight:700;
                text-transform:uppercase;letter-spacing:0.8px;color:var(--color-primary);
                text-align:left;border-bottom:1px solid var(--color-border);">
                ${_esc(fieldMeta(col).label)}</th>`;
        }
        html += `<th style="padding:10px var(--space-4);font-size:11px;font-weight:700;
            text-transform:uppercase;letter-spacing:0.8px;color:var(--color-primary);
            text-align:right;border-bottom:1px solid var(--color-border);">Members</th>
                </tr></thead><tbody>`;

        for (const row of result.rows) {
            html += `<tr style="border-bottom:1px solid var(--color-border);">`;
            for (const col of result.columns) {
                html += `<td style="padding:9px var(--space-4);font-size:var(--font-size-sm);
                    color:var(--color-text-body);">${_esc(row[col] ?? '—')}</td>`;
            }
            html += `<td style="padding:9px var(--space-4);font-size:var(--font-size-sm);
                font-weight:var(--font-weight-bold);color:var(--color-primary);
                text-align:right;">${row.member_count.toLocaleString()}</td>
            </tr>`;
        }
        html += `</tbody></table></div>`;
    }

    resultArea.innerHTML = html;
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiFetch(url, opts = {}) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
}

// ── Actions ───────────────────────────────────────────────────────────────────

async function loadCatalogue() {
    const data = await apiFetch('/api/custom-reports/fields');
    S.catalogue = data.fields;
}

async function loadSavedReports() {
    const data = await apiFetch('/api/custom-reports/');
    S.savedReports = data.reports;
    renderSavedBar();
}

async function loadReport(id) {
    const data = await apiFetch(`/api/custom-reports/${id}`);
    S.reportId   = data.id;
    S.reportName = data.name;
    S.dimensions = data.definition.dimensions;
    S.filters    = data.definition.filters || {};
    nameInput.value = S.reportName;
    history.replaceState(null, '', `/reports/builder/${id}`);
    renderLeft();
    renderSavedBar();
    renderEmptyResult();
}

function resetState() {
    S.reportId   = null;
    S.reportName = '';
    S.dimensions = [];
    S.filters    = {};
    nameInput.value = '';
    history.replaceState(null, '', '/reports/builder/new');
    renderLeft();
    renderSavedBar();
    renderEmptyResult();
}

async function saveReport() {
    const name = nameInput.value.trim();
    if (!name) {
        nameInput.focus();
        nameInput.style.borderColor = 'var(--color-error)';
        setTimeout(() => { nameInput.style.borderColor = ''; }, 2000);
        return;
    }
    if (S.dimensions.length === 0) {
        alert('Please select at least one field to group by.');
        return;
    }
    const body = {
        name,
        definition: { dimensions: S.dimensions, filters: S.filters },
    };
    try {
        let data;
        if (S.reportId) {
            data = await apiFetch(`/api/custom-reports/${S.reportId}`, {
                method: 'POST',
                body: JSON.stringify(body),
            });
        } else {
            data = await apiFetch('/api/custom-reports/', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            S.reportId = data.id;
            history.replaceState(null, '', `/reports/builder/${S.reportId}`);
        }
        S.reportName = data.name;
        await loadSavedReports();
    } catch (err) {
        alert(`Save failed: ${err.message}`);
    }
}

async function runReport() {
    if (S.dimensions.length === 0) {
        alert('Please select at least one field to group by.');
        return;
    }
    const btnRun = document.getElementById('btn-run');
    btnRun.disabled  = true;
    btnRun.textContent = 'Running…';
    try {
        let result;
        if (S.reportId) {
            result = await apiFetch(`/api/custom-reports/${S.reportId}/run`, {
                method: 'POST',
            });
        } else {
            result = await apiFetch('/api/custom-reports/run', {
                method: 'POST',
                body: JSON.stringify({
                    dimensions: S.dimensions,
                    filters: S.filters,
                }),
            });
        }
        renderResult(result);
    } catch (err) {
        resultArea.innerHTML = `
            <div style="color:var(--color-error);padding:var(--space-4);">
                Error: ${_esc(err.message)}
            </div>`;
    } finally {
        btnRun.disabled = false;
        btnRun.textContent = '▶ Run';
    }
}

// ── Initialisation ────────────────────────────────────────────────────────────

async function init() {
    try {
        await loadCatalogue();
        await loadSavedReports();
    } catch (err) {
        leftPanel.innerHTML = `
            <div style="color:var(--color-error);font-size:var(--font-size-sm);
                        padding:var(--space-4);">
                Failed to load fields: ${_esc(err.message)}
            </div>`;
        return;
    }

    const initialReportId = ROOT.dataset.reportId;
    if (initialReportId) {
        try {
            await loadReport(initialReportId);
        } catch {
            // Report not found or not owned — start fresh
            resetState();
        }
    } else {
        renderLeft();
        renderEmptyResult();
    }

    document.getElementById('btn-new').addEventListener('click', resetState);
    document.getElementById('btn-save').addEventListener('click', saveReport);
    document.getElementById('btn-run').addEventListener('click', runReport);
}

document.addEventListener('DOMContentLoaded', init);
```

- [ ] **Step 2: Test the builder manually**

Start the dev server:
```bash
cd app
uvicorn main:app --reload --port 8000
```

Visit `http://localhost:8000/reports/builder`. Verify:
1. Left panel shows 6 field pills (Country, Gender, Age Band, CSF Leak Type, Cause Group, Individual Cause)
2. Clicking a pill toggles it active and shows ordinal badge (1st, 2nd, …)
3. An active dimension gains a filter dropdown below
4. "Filter on another field" select appears for non-dimension fields
5. Pressing Run with no dimensions selected shows the alert
6. Pressing Run with dimensions selected calls the API and renders a table
7. Suppression notice appears when `suppressed_count > 0`
8. Entering a name and pressing Save creates the report; URL updates to `/reports/builder/{id}`
9. Saved chip appears in the bar; clicking it reloads the definition
10. Pressing New resets state and clears the URL to `/reports/builder/new`

- [ ] **Step 3: Commit**

```bash
git add static/js/report_builder.js
git commit -m "feat: replace report_builder.js with query builder UI"
```

---

## Task 6: Delete blocks.py

**Files:**
- Delete: `app/reports/blocks.py`

- [ ] **Step 1: Verify no remaining imports of `reports.blocks`**

```bash
cd app
grep -r "reports.blocks\|from reports import blocks\|from reports.blocks" . --include="*.py"
```

Expected: no output (custom_reports.py no longer imports it).

- [ ] **Step 2: Delete the file**

```bash
rm app/reports/blocks.py
```

- [ ] **Step 3: Run the full non-DB test suite — confirm no regressions**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest tests/ \
  --ignore=tests/test_reports --tb=short -q 2>&1 | tail -10
```

Expected: all previously-passing tests still pass. The old `TestBlockRegistry` tests are gone (replaced in Task 1), so their absence is expected.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete blocks.py — no longer used after query builder rewrite"
```

---

## Task 7: DB-Dependent Tests

**Files:**
- Modify: `app/tests/test_api/test_custom_reports.py` (append DB test classes)

These tests require the test PostgreSQL instance (`csfleak_test`). They will error locally if the DB is unavailable — that is expected. They pass in CI.

- [ ] **Step 1: Append DB test classes to the test file**

```python
class TestFieldsEndpoint:
    """DB-dependent: queries distinct values for dynamic fields."""

    async def test_fields_returns_six_fields(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        assert response.status_code == 200
        data = response.json()
        assert len(data["fields"]) == 6

    async def test_field_keys_in_correct_order(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        keys = [f["key"] for f in response.json()["fields"]]
        assert keys == [
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        ]

    async def test_each_field_has_key_label_values(
        self, researcher_client
    ) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        for field in response.json()["fields"]:
            assert "key" in field
            assert "label" in field
            assert isinstance(field["values"], list)

    async def test_leak_type_enum_values(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        lt = next(
            f for f in response.json()["fields"] if f["key"] == "leak_type"
        )
        assert set(lt["values"]) == {
            "spinal", "cranial", "spinalAndCranial", "unknown"
        }


class TestRunEndpoint:
    """DB-dependent: exercises the query builder end-to-end."""

    async def test_run_returns_correct_shape(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == ["country"]
        assert "rows" in data
        assert "total_shown" in data
        assert "suppressed_count" in data
        assert isinstance(data["suppressed_count"], int)

    async def test_run_result_rows_respect_k10(
        self, researcher_client
    ) -> None:
        """All returned rows must have member_count >= 10."""
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        for row in response.json()["rows"]:
            assert row["member_count"] >= 10

    async def test_run_with_filter_narrows_results(
        self, researcher_client
    ) -> None:
        """Running with a country filter must only return rows for that country."""
        full = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country", "gender"]},
        )
        # Apply filter to first country in the full result (if any)
        rows = full.json()["rows"]
        if not rows:
            return  # no data in test DB — skip
        first_country = rows[0]["country"]
        filtered = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": ["country", "gender"],
                "filters": {"country": [first_country]},
            },
        )
        for row in filtered.json()["rows"]:
            assert row["country"] == first_country


class TestCustomReportCRUD:
    """DB-dependent: full CRUD lifecycle."""

    _defn = {"dimensions": ["country", "gender"]}

    async def test_create_returns_201(self, researcher_client) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Test Report", "definition": self._defn},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Report"
        assert "id" in data
        assert data["definition"]["dimensions"] == ["country", "gender"]

    async def test_list_returns_own_reports_only(
        self, researcher_client, admin_client
    ) -> None:
        await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Researcher Report", "definition": self._defn},
        )
        admin_list = await admin_client.get("/api/custom-reports/")
        names = [r["name"] for r in admin_list.json()["reports"]]
        assert "Researcher Report" not in names

    async def test_get_own_report_returns_200(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "My Report", "definition": self._defn},
        )
        report_id = create.json()["id"]
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 200
        assert get.json()["name"] == "My Report"

    async def test_get_other_users_report_returns_404(
        self, researcher_client, admin_client
    ) -> None:
        create = await admin_client.post(
            "/api/custom-reports/",
            json={"name": "Admin Report", "definition": self._defn},
        )
        report_id = create.json()["id"]
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 404

    async def test_delete_own_report_returns_204(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Delete Me", "definition": self._defn},
        )
        report_id = create.json()["id"]
        delete = await researcher_client.post(
            f"/api/custom-reports/{report_id}/delete"
        )
        assert delete.status_code == 204
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 404

    async def test_run_saved_report_returns_query_result(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Run Me", "definition": self._defn},
        )
        report_id = create.json()["id"]
        run = await researcher_client.post(
            f"/api/custom-reports/{report_id}/run"
        )
        assert run.status_code == 200
        data = run.json()
        assert data["columns"] == ["country", "gender"]
        assert "suppressed_count" in data
        assert data["report_id"] == report_id

    async def test_run_includes_suppressed_count(
        self, researcher_client
    ) -> None:
        """High-cardinality definition maximises suppression probability."""
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={
                "name": "High Cardinality",
                "definition": {
                    "dimensions": [
                        "country", "gender", "age_band",
                        "leak_type", "cause_group",
                    ]
                },
            },
        )
        report_id = create.json()["id"]
        run = await researcher_client.post(
            f"/api/custom-reports/{report_id}/run"
        )
        assert run.status_code == 200
        assert isinstance(run.json()["suppressed_count"], int)
```

- [ ] **Step 2: Run the non-DB subset — confirm still all passing**

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest \
  tests/test_api/test_custom_reports.py::TestQueryBuilderUnit \
  tests/test_api/test_custom_reports.py::TestCustomReportAuth \
  tests/test_api/test_custom_reports.py::TestQueryDefinitionValidation \
  tests/test_api/test_custom_reports.py::TestUIRoutes -v
```

Expected: all 23 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_custom_reports.py
git commit -m "test: add DB-dependent tests for fields endpoint, run, and CRUD"
```

---

## Done

All tasks complete. Run the full non-DB suite one final time:

```bash
cd app
/Users/stevehamilton/Documents/Claude/CSFLA\ Data/app/.venv/bin/pytest tests/ \
  --ignore=tests/test_reports --tb=short -q 2>&1 | tail -5
```

Expected: same or better pass count vs baseline (209 passed before this work).
