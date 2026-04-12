"""
Shared fixtures and seeding helpers for report integration tests.

All data is inserted directly via ORM (no pipeline) to give tests precise
control over counts. Each Member requires an ImportBatch FK; child tables
also require import_batch_id.

After seeding, always call `await db.flush()` so that subsequent raw-SQL
queries (used by report modules) can see the rows within the same transaction.
"""

from __future__ import annotations
import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CauseOfLeak, CSFLeakType, ImportBatch, Member, MemberStatus


# ── Low-level helpers ─────────────────────────────────────────────────────────

async def _make_batch(db: AsyncSession) -> ImportBatch:
    """Insert a minimal ImportBatch and return it (unflushed)."""
    batch = ImportBatch(
        batch_id=uuid.uuid4(),
        imported_by="00000000-0000-0000-0000-test00000000",
        source_filename="test_fixture.csv",
        total_records=1,
        imported_records=1,
        skipped_records=0,
        rejected_records=0,
    )
    db.add(batch)
    return batch


async def _make_member(
    db: AsyncSession,
    batch_id: uuid.UUID,
    pseudo_id: str,
    *,
    country: str = "England",
    gender: str | None = "female",
    age_band: str | None = "30_39",
    region: str | None = "London",
    outward_code: str | None = "SW1A",
    member_since_year: int | None = 2020,
    referral_source: list[str] | None = None,
) -> Member:
    """Insert a Member row and return it (unflushed)."""
    m = Member(
        pseudo_id=pseudo_id,
        country=country,
        gender=gender,
        age_band=age_band,
        region=region,
        outward_code=outward_code,
        member_since_year=member_since_year,
        referral_source=referral_source,
        first_seen_batch=batch_id,
        last_updated_batch=batch_id,
    )
    db.add(m)
    return m


async def _add_status(
    db: AsyncSession,
    batch_id: uuid.UUID,
    pseudo_id: str,
    status: str,
) -> None:
    db.add(MemberStatus(
        id=uuid.uuid4(),
        pseudo_id=pseudo_id,
        status_value=status,
        import_batch_id=batch_id,
    ))


async def _add_leak_type(
    db: AsyncSession,
    batch_id: uuid.UUID,
    pseudo_id: str,
    leak_type: str,
) -> None:
    db.add(CSFLeakType(
        id=uuid.uuid4(),
        pseudo_id=pseudo_id,
        leak_type=leak_type,
        import_batch_id=batch_id,
    ))


async def _add_cause(
    db: AsyncSession,
    batch_id: uuid.UUID,
    pseudo_id: str,
    cause: str,
) -> None:
    db.add(CauseOfLeak(
        id=uuid.uuid4(),
        pseudo_id=pseudo_id,
        cause=cause,
        import_batch_id=batch_id,
    ))


# ── Standard cohort fixture ───────────────────────────────────────────────────
#
# Inserts a cohort designed to satisfy all report tests:
#
#   - 12 England/female/30_39/spinal/csfLeakSuffererDiagnosed (k≥10 for England)
#   - 9 Scotland/male/40_49/cranial/csfLeakSuffererSuspected (k<10 – below threshold)
#   - 2 Germany/female/50_59/spinalAndCranial/formerCsfLeakSufferer
#   - 1 France/female/20_29/unknown/csfLeakSuffererDiagnosed
#
# Causes split:
#   - England group: ehlersDanlosSyndrome (Connective Tissue Disorder)
#   - Scotland group: lumbarPuncture (Iatrogenic)
#   - German/French: trauma (Traumatic) + spinalSurgery (Iatrogenic)
#
# Referral sources:
#   - England group: 12 with ["socialMedia"]
#   - Scotland group: 9 with ["gp"]
#   - Remaining 3: None (NULL)
#
# Yields a dict with useful counts and the batch_id for use in individual tests.

@pytest_asyncio.fixture
async def standard_cohort(db_session: AsyncSession) -> dict:
    batch = await _make_batch(db_session)
    await db_session.flush()
    bid = batch.batch_id

    members_created: list[str] = []

    # 12 England, female, diagnosed, spinal, EDS
    for i in range(12):
        pid = f"eng-f-{i:04d}"
        await _make_member(
            db_session, bid, pid,
            country="England", gender="female", age_band="30_39",
            region="London", outward_code="SW1A", member_since_year=2020,
            referral_source=["socialMedia"],
        )
        await _add_status(db_session, bid, pid, "csfLeakSuffererDiagnosed")
        await _add_leak_type(db_session, bid, pid, "spinal")
        await _add_cause(db_session, bid, pid, "ehlersDanlosSyndrome")
        members_created.append(pid)

    # 9 Scotland, male, suspected, cranial, lumbarPuncture
    for i in range(9):
        pid = f"sco-m-{i:04d}"
        await _make_member(
            db_session, bid, pid,
            country="Scotland", gender="male", age_band="40_49",
            region="Lothian", outward_code="EH1", member_since_year=2021,
            referral_source=["gp"],
        )
        await _add_status(db_session, bid, pid, "csfLeakSuffererSuspected")
        await _add_leak_type(db_session, bid, pid, "cranial")
        await _add_cause(db_session, bid, pid, "lumbarPuncture")
        members_created.append(pid)

    # 2 Germany, female, formerSufferer, spinalAndCranial, trauma + spinalSurgery
    for i in range(2):
        pid = f"deu-f-{i:04d}"
        await _make_member(
            db_session, bid, pid,
            country="Germany", gender="female", age_band="50_59",
            region=None, outward_code=None, member_since_year=2022,
            referral_source=None,
        )
        await _add_status(db_session, bid, pid, "formerCsfLeakSufferer")
        await _add_leak_type(db_session, bid, pid, "spinalAndCranial")
        await _add_cause(db_session, bid, pid, "trauma")
        await _add_cause(db_session, bid, pid, "spinalSurgery")
        members_created.append(pid)

    # 1 France, female, diagnosed, unknown leak type, spinalSurgery
    pid = "fra-f-0000"
    await _make_member(
        db_session, bid, pid,
        country="France", gender="female", age_band="20_29",
        region=None, outward_code=None, member_since_year=2023,
        referral_source=None,
    )
    await _add_status(db_session, bid, pid, "csfLeakSuffererDiagnosed")
    await _add_leak_type(db_session, bid, pid, "unknown")
    await _add_cause(db_session, bid, pid, "spinalSurgery")
    members_created.append(pid)

    await db_session.flush()

    return {
        "batch_id": bid,
        "total": len(members_created),          # 24
        "england_count": 12,
        "scotland_count": 9,
        "germany_count": 2,
        "france_count": 1,
        "pseudo_ids": members_created,
    }
