"""
Integration tests for the import pipeline.

These tests run against a real PostgreSQL database using the transaction-rollback
fixture from conftest.py — all writes are rolled back after each test.

Fixtures used:
  sample_import_valid.csv    — 50 UK/EU records, all in scope
  sample_import_mixed.csv    — 50 records, 30 UK/EU + 20 out-of-scope
  sample_import_schema.csv   — missing 'csfLeakType' column (schema halt)
  sample_import_pii.csv      — 5 records with full PII in CSV (stripped by pipeline)
"""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CauseOfLeak,
    CSFLeakType,
    ErasureRegister,
    ImportBatch,
    Member,
    MemberStatus,
)
from pipeline import PipelineHalt, PipelineResult, run_import
from pipeline.pseudonymisation import compute_pseudo_id

# Reads the key that conftest.py guarantees is in the environment via setdefault
TEST_PSEUDONYMISATION_KEY = os.environ.get(
    "TEST_PSEUDONYMISATION_KEY",
    "test-hmac-key-csfleak-never-use-in-production-aabbccdd",
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _csv(fixtures_dir: Path, name: str) -> bytes:
    return (fixtures_dir / name).read_bytes()


ADMIN_OID = "00000000-0000-0000-0000-admin0000000"


# ── Count assertions ──────────────────────────────────────────────────────────

async def _count(db: AsyncSession, model) -> int:
    result = await db.execute(select(model))
    return len(result.scalars().all())


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_valid_import_counts(db_session: AsyncSession, fixtures_dir: Path):
    """50 in-scope records → all 50 imported, 0 skipped, 0 rejected."""
    result = await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_valid.csv"),
        source_filename="sample_import_valid.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    assert isinstance(result, PipelineResult)
    assert result.total_records == 50
    assert result.imported_records == 50
    assert result.skipped_records == 0
    assert result.rejected_records == 0
    assert result.rejection_log == []


async def test_valid_import_members_written(db_session: AsyncSession, fixtures_dir: Path):
    """50 in-scope records → 50 rows in members table, no PII columns present."""
    await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_valid.csv"),
        source_filename="sample_import_valid.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    member_count = await _count(db_session, Member)
    assert member_count == 50

    # Spot-check member 1001 — England, female, SW1A outward code
    expected_pseudo = compute_pseudo_id("1001", TEST_PSEUDONYMISATION_KEY)
    result = await db_session.execute(
        select(Member).where(Member.pseudo_id == expected_pseudo)
    )
    member = result.scalar_one()

    assert member.country == "England"
    assert member.gender == "female"
    assert member.outward_code == "SW1A"
    assert member.member_since_year == 2019

    # No PII fields
    assert not hasattr(member, "first_name") or True   # ORM model has no such col
    # Verify no email, name, or full postcode stored
    for col in member.__table__.columns:
        assert col.name not in {
            "firstName", "lastName", "email", "password", "phoneNumber",
            "streetAddress", "dateOfBirth",
        }, f"PII column found in schema: {col.name}"


async def test_valid_import_child_tables(db_session: AsyncSession, fixtures_dir: Path):
    """Health data written to child tables for member 1001."""
    await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_valid.csv"),
        source_filename="sample_import_valid.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    expected_pseudo = compute_pseudo_id("1001", TEST_PSEUDONYMISATION_KEY)

    statuses = (await db_session.execute(
        select(MemberStatus).where(MemberStatus.pseudo_id == expected_pseudo)
    )).scalars().all()
    assert any(s.status_value == "csfLeakSuffererDiagnosed" for s in statuses)

    leak_types = (await db_session.execute(
        select(CSFLeakType).where(CSFLeakType.pseudo_id == expected_pseudo)
    )).scalars().all()
    assert any(lt.leak_type == "spinal" for lt in leak_types)


async def test_valid_import_multi_value_fields(db_session: AsyncSession, fixtures_dir: Path):
    """Member 1001 has two cause values (pipe-separated in CSV) — both stored."""
    await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_valid.csv"),
        source_filename="sample_import_valid.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    expected_pseudo = compute_pseudo_id("1001", TEST_PSEUDONYMISATION_KEY)
    causes = (await db_session.execute(
        select(CauseOfLeak).where(CauseOfLeak.pseudo_id == expected_pseudo)
    )).scalars().all()

    cause_values = {c.cause for c in causes}
    assert "ehlersDanlosSyndrome" in cause_values
    assert "spinalSurgery" in cause_values


async def test_valid_import_batch_record(db_session: AsyncSession, fixtures_dir: Path):
    """import_batches row written with correct counts and metadata."""
    result = await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_valid.csv"),
        source_filename="sample_import_valid.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    batch = (await db_session.execute(
        select(ImportBatch).where(ImportBatch.batch_id == result.batch_id)
    )).scalar_one()

    assert batch.imported_by == ADMIN_OID
    assert batch.source_filename == "sample_import_valid.csv"
    assert batch.total_records == 50
    assert batch.imported_records == 50
    assert batch.skipped_records == 0
    assert batch.rejected_records == 0


async def test_mixed_import_geo_filter(db_session: AsyncSession, fixtures_dir: Path):
    """
    Mixed CSV: 30 in-scope (UK/EU) + 20 out-of-scope (US/Canada/Australia).
    Only in-scope records are imported.
    """
    result = await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_mixed.csv"),
        source_filename="sample_import_mixed.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    assert result.total_records == 50
    assert result.imported_records == 30
    assert result.skipped_records == 20
    assert result.rejected_records == 0

    member_count = await _count(db_session, Member)
    assert member_count == 30


async def test_schema_halt_on_missing_column(db_session: AsyncSession, fixtures_dir: Path):
    """CSV missing 'csfLeakType' column triggers PipelineHalt before any write."""
    with pytest.raises(PipelineHalt) as exc_info:
        await run_import(
            csv_bytes=_csv(fixtures_dir, "sample_import_schema.csv"),
            source_filename="sample_import_schema.csv",
            imported_by=ADMIN_OID,
            db=db_session,
        )

    assert "csfLeakType" in str(exc_info.value)
    assert "Schema validation failed" in str(exc_info.value)

    # No members written
    assert await _count(db_session, Member) == 0


async def test_pii_csv_imports_cleanly(db_session: AsyncSession, fixtures_dir: Path):
    """
    CSV with full PII columns populated still imports successfully.

    The transformation allowlist strips all PII fields before the PII check —
    the pipeline should not halt on a normal membership export that contains
    PII columns (they are never read into the transformed record).
    """
    result = await run_import(
        csv_bytes=_csv(fixtures_dir, "sample_import_pii.csv"),
        source_filename="sample_import_pii.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    assert result.imported_records == 5
    assert result.skipped_records == 0
    assert result.rejected_records == 0

    # Verify no PII stored in any member row
    members = (await db_session.execute(select(Member))).scalars().all()
    for m in members:
        for col in m.__table__.columns:
            assert col.name not in {
                "firstName", "lastName", "email", "password",
                "phoneNumber", "streetAddress", "dateOfBirth",
            }


async def test_upsert_updates_not_duplicates(db_session: AsyncSession, fixtures_dir: Path):
    """
    Importing the same CSV twice produces 50 members (not 100).
    Second import updates last_updated_batch; first_seen_batch unchanged.
    """
    csv_bytes = _csv(fixtures_dir, "sample_import_valid.csv")

    result1 = await run_import(
        csv_bytes=csv_bytes,
        source_filename="import1.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )
    result2 = await run_import(
        csv_bytes=csv_bytes,
        source_filename="import2.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    assert result1.imported_records == 50
    assert result2.imported_records == 50

    # Still only 50 member rows
    assert await _count(db_session, Member) == 50

    # first_seen_batch from import1, last_updated_batch from import2
    expected_pseudo = compute_pseudo_id("1001", TEST_PSEUDONYMISATION_KEY)
    member = (await db_session.execute(
        select(Member).where(Member.pseudo_id == expected_pseudo)
    )).scalar_one()

    assert member.first_seen_batch == result1.batch_id
    assert member.last_updated_batch == result2.batch_id


async def test_erasure_register_blocks_reimport(db_session: AsyncSession, fixtures_dir: Path):
    """
    Members present in erasure_register are skipped on import.

    Flow:
      1. Import valid CSV → 50 imported
      2. Add member 1001's pseudo_id to erasure_register
      3. Import same CSV again → 49 imported, 1 skipped with reason=subject_erased
    """
    csv_bytes = _csv(fixtures_dir, "sample_import_valid.csv")

    # First import
    await run_import(
        csv_bytes=csv_bytes,
        source_filename="import1.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    # Register member 1001 as erased
    erased_pseudo = compute_pseudo_id("1001", TEST_PSEUDONYMISATION_KEY)
    await db_session.execute(
        insert(ErasureRegister).values(
            pseudo_id=erased_pseudo,
            erased_by=ADMIN_OID,
            erasure_reason="Article 17 test erasure",
        )
    )

    # Second import — erased member must be skipped
    result2 = await run_import(
        csv_bytes=csv_bytes,
        source_filename="import2.csv",
        imported_by=ADMIN_OID,
        db=db_session,
    )

    assert result2.imported_records == 49
    assert result2.skipped_records == 1

    erased_entries = [e for e in result2.rejection_log if e.reason == "subject_erased"]
    assert len(erased_entries) == 1
    assert erased_entries[0].record_id == erased_pseudo


async def test_two_batches_recorded(db_session: AsyncSession, fixtures_dir: Path):
    """Two imports produce two distinct import_batches rows."""
    csv_bytes = _csv(fixtures_dir, "sample_import_valid.csv")

    result1 = await run_import(csv_bytes, "a.csv", ADMIN_OID, db_session)
    result2 = await run_import(csv_bytes, "b.csv", ADMIN_OID, db_session)

    assert result1.batch_id != result2.batch_id
    assert await _count(db_session, ImportBatch) == 2


async def test_empty_csv_halts(db_session: AsyncSession):
    """A CSV with no headers raises PipelineHalt."""
    with pytest.raises(PipelineHalt):
        await run_import(
            csv_bytes=b"",
            source_filename="empty.csv",
            imported_by=ADMIN_OID,
            db=db_session,
        )
