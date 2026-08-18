"""
Integration tests for GET /api/admin/export.

Covers:
  - Role enforcement (admin only)
  - Acknowledgement gate
  - CSV / JSON / NDJSON success paths
  - Audit row written on success
  - Rate limiting (one successful export per 24h)
  - Suppression of small-count combinations
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ExportAudit

# ── Seeding helpers (imported directly — not fixtures) ────────────────────────
from tests.test_reports.conftest import (
    _make_batch,
    _make_member,
    _add_status,
    _add_leak_type,
    _add_cause,
)

# The admin OID produced by conftest._make_user("admin")
ADMIN_OID = "00000000-0000-0000-0000-admin0000000"

EXPORT_URL = "/api/admin/export"


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _seed_large_cohort(db: AsyncSession) -> dict:
    """
    Seed 12 members all sharing the same (age_band, gender, country, cause_group)
    combination so none are suppressed, plus a batch reference.
    """
    batch = await _make_batch(db)
    await db.flush()
    bid = batch.batch_id

    for i in range(12):
        pid = f"export-test-{i:04d}"
        await _make_member(
            db, bid, pid,
            country="England", gender="female", age_band="26_34",
            region="London", outward_code="SW1A", member_since_year=2021,
            referral_source=["socialMedia"],
        )
        await _add_status(db, bid, pid, "csfLeakSuffererDiagnosed")
        await _add_leak_type(db, bid, pid, "spinal")
        await _add_cause(db, bid, pid, "ehlersDanlosSyndrome")

    await db.flush()
    return {"batch_id": bid, "count": 12}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_csv_requires_admin(researcher_client: AsyncClient):
    """Researcher role must receive 403."""
    resp = await researcher_client.get(EXPORT_URL, params={"format": "csv", "acknowledged": "true"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_requires_acknowledgement(admin_client: AsyncClient, db_session: AsyncSession):
    """GET without acknowledged=true returns 400."""
    await _seed_large_cohort(db_session)
    resp = await admin_client.get(EXPORT_URL, params={"format": "csv"})
    assert resp.status_code == 400
    assert "acknowledged" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_export_csv_success(admin_client: AsyncClient, db_session: AsyncSession):
    """CSV export returns correct headers and rows; no pseudo_id, no outward_code."""
    await _seed_large_cohort(db_session)
    resp = await admin_client.get(EXPORT_URL, params={"format": "csv", "acknowledged": "true"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")

    # Strip BOM and parse
    content = resp.text.lstrip("\ufeff")
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) >= 2  # header + at least one data row

    header = lines[0].split(",")
    assert "row_id" in header
    assert "pseudo_id" not in header
    assert "outward_code" not in header
    assert "age_band" in header
    assert "gender" in header
    assert "country" in header


@pytest.mark.asyncio
async def test_export_json_success(admin_client: AsyncClient, db_session: AsyncSession):
    """JSON export includes top-level wrapper keys and correct record structure."""
    await _seed_large_cohort(db_session)
    resp = await admin_client.get(EXPORT_URL, params={"format": "json", "acknowledged": "true"})
    assert resp.status_code == 200

    body = resp.json()
    assert "exported_at" in body
    assert "record_count" in body
    assert "suppressed_count" in body
    assert "records" in body
    assert isinstance(body["records"], list)
    assert body["record_count"] == len(body["records"])

    # Verify record structure
    if body["records"]:
        rec = body["records"][0]
        assert "row_id" in rec
        assert "pseudo_id" not in rec
        assert "outward_code" not in rec
        assert "age_band" in rec
        assert "statuses" in rec
        assert "leak_types" in rec
        assert "causes" in rec
        # Arrays should be lists
        assert isinstance(rec["statuses"], list)
        assert isinstance(rec["causes"], list)


@pytest.mark.asyncio
async def test_export_ndjson_success(admin_client: AsyncClient, db_session: AsyncSession):
    """NDJSON export: each line parses as a valid JSON object."""
    await _seed_large_cohort(db_session)
    resp = await admin_client.get(EXPORT_URL, params={"format": "ndjson", "acknowledged": "true"})
    assert resp.status_code == 200
    assert "ndjson" in resp.headers["content-type"]

    lines = [l for l in resp.text.splitlines() if l.strip()]
    assert len(lines) >= 1

    for line in lines:
        obj = json.loads(line)
        assert "row_id" in obj
        assert "pseudo_id" not in obj
        assert "country" in obj


@pytest.mark.asyncio
async def test_export_audit_row_written(admin_client: AsyncClient, db_session: AsyncSession):
    """After a successful export, an ExportAudit row exists with correct fields."""
    await _seed_large_cohort(db_session)
    resp = await admin_client.get(EXPORT_URL, params={"format": "csv", "acknowledged": "true"})
    assert resp.status_code == 200

    result = await db_session.execute(
        select(ExportAudit).where(
            ExportAudit.exported_by == ADMIN_OID,
            ExportAudit.outcome == "success",
        )
    )
    audit_row = result.scalar_one_or_none()
    assert audit_row is not None
    assert audit_row.format == "csv"
    assert audit_row.row_count > 0
    assert audit_row.acknowledged is True
    assert audit_row.outcome == "success"


@pytest.mark.asyncio
async def test_export_rate_limit(admin_client: AsyncClient, db_session: AsyncSession):
    """If a successful export exists within 24h, return 429."""
    await _seed_large_cohort(db_session)

    # Seed an existing successful export audit row for this admin within the last 24h
    db_session.add(ExportAudit(
        id=uuid.uuid4(),
        exported_by=ADMIN_OID,
        exported_at=datetime.now(timezone.utc) - timedelta(hours=1),
        format="csv",
        row_count=12,
        suppressed_count=0,
        client_ip="127.0.0.1",
        outcome="success",
        acknowledged=True,
    ))
    await db_session.flush()

    resp = await admin_client.get(EXPORT_URL, params={"format": "csv", "acknowledged": "true"})
    assert resp.status_code == 429
    assert "limit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_export_suppression(admin_client: AsyncClient, db_session: AsyncSession):
    """
    A member with a unique combination (count=1, below threshold of 10) should
    not appear in the export, and suppressed_count should reflect this.
    """
    batch = await _make_batch(db_session)
    await db_session.flush()
    bid = batch.batch_id

    # Seed 12 unsuppressed members (England/female/26_34/ehlersDanlosSyndrome)
    for i in range(12):
        pid = f"supp-ok-{i:04d}"
        await _make_member(
            db_session, bid, pid,
            country="England", gender="female", age_band="26_34",
        )
        await _add_cause(db_session, bid, pid, "ehlersDanlosSyndrome")

    # Seed 1 member with a unique combination that will be suppressed
    # Unique: Wales / nonbinary gender / 18_25 / trauma → count=1 → suppressed
    unique_pid = "supp-unique-0000"
    await _make_member(
        db_session, bid, unique_pid,
        country="Wales", gender="nonbinary", age_band="18_25",
    )
    await _add_cause(db_session, bid, unique_pid, "trauma")

    await db_session.flush()

    resp = await admin_client.get(EXPORT_URL, params={"format": "json", "acknowledged": "true"})
    assert resp.status_code == 200

    body = resp.json()
    assert body["suppressed_count"] > 0

    # The unique member must not appear in the records
    for rec in body["records"]:
        assert not (
            rec["country"] == "Wales"
            and rec["gender"] == "nonbinary"
            and rec["age_band"] == "18_25"
        ), "Suppressed member appeared in export"
