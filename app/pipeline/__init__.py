"""
Import pipeline — ETL from membership CSV to research database.

Implements the 7-step flow from Data Architecture Spec v0.3 Section 7.2:

  1. Geographic filter  — drop non-UK/EEA records, log count
  2. Schema validation  — halt if required columns are missing
  3. Record validation  — skip invalid records, log reason
  4. Pseudonymisation   — HMAC-SHA256 per spec Section 5
  5. Field transform    — allowlist transform, PII check (hard halt on failure)
  6. Upsert             — members + child tables, erasure register check
  7. Batch summary      — import_batches record with final counts

The caller (API endpoint or test) is responsible for committing or rolling
back the database session. This function does NOT call commit().
"""

from __future__ import annotations
import csv
import io
import uuid
from dataclasses import dataclass, field as dc_field

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    CauseOfLeak,
    CSFLeakType,
    ErasureRegister,
    ImportBatch,
    Member,
    MemberStatus,
)
from pipeline.geographic_filter import is_in_scope
from pipeline.pii_check import check_for_pii
from pipeline.pseudonymisation import compute_pseudo_id
from pipeline.field_transform import (
    normalise_gender,
    to_age_band,
    to_membership_year,
    to_outward_code,
)


# ── Constants ─────────────────────────────────────────────────────────────────

#: Source CSV columns that must be present for the pipeline to proceed.
#: Any missing column triggers a PipelineHalt before any records are processed.
REQUIRED_COLUMNS: frozenset[str] = frozenset({
    "id",
    "dateOfBirth",
    "gender",
    "country",
    "postcodeZipCode",
    "memberStatus",
    "csfLeakType",
    "causeOfLeak",
    "memberSince",
    "referralSource",
})


# ── Result types ──────────────────────────────────────────────────────────────

class PipelineHalt(Exception):
    """
    Raised when the import pipeline encounters a hard-stop condition.

    Conditions that trigger a halt:
      - Required CSV column missing (schema change)
      - PII detected in a transformed record
      - Pseudonymisation key unavailable

    On this path no database writes have been committed.
    """


@dataclass
class RejectionEntry:
    """A single record-level rejection or skip event."""
    record_id: str
    reason: str
    detail: str = ""


@dataclass
class PipelineResult:
    """Summary returned by run_import on successful completion."""
    batch_id: uuid.UUID
    total_records: int
    imported_records: int
    skipped_records: int
    rejected_records: int
    rejection_log: list[RejectionEntry] = dc_field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_pipe_list(value: str | None) -> list[str]:
    """Split a pipe-separated string into a list. Returns [] for empty/None."""
    if not value or not value.strip():
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def _filter_vocab(
    values: list[str], valid: frozenset[str]
) -> tuple[list[str], list[str]]:
    """Partition values into (valid, invalid) against a controlled vocabulary."""
    valid_vals = [v for v in values if v in valid]
    invalid_vals = [v for v in values if v not in valid]
    return valid_vals, invalid_vals


def _transform_record(row: dict) -> tuple[dict, dict, list[str]]:
    """
    Transform a raw CSV row into research-safe field dicts.

    Returns:
        member_data:  fields for the members table
        health_data:  dict with keys 'statuses', 'leak_types', 'causes'
        warnings:     non-fatal validation messages (unrecognised vocab values)
    """
    warnings: list[str] = []

    # Multi-value health fields are pipe-separated in the CSV
    raw_statuses = _parse_pipe_list(row.get("memberStatus"))
    raw_leak_types = _parse_pipe_list(row.get("csfLeakType"))
    raw_causes = _parse_pipe_list(row.get("causeOfLeak"))

    statuses, bad_statuses = _filter_vocab(raw_statuses, MemberStatus.VALID_VALUES)
    leak_types, bad_leak_types = _filter_vocab(raw_leak_types, CSFLeakType.VALID_VALUES)
    causes, bad_causes = _filter_vocab(raw_causes, CauseOfLeak.VALID_VALUES)

    for v in bad_statuses:
        warnings.append(f"memberStatus: unrecognised value '{v}'")
    for v in bad_leak_types:
        warnings.append(f"csfLeakType: unrecognised value '{v}'")
    for v in bad_causes:
        warnings.append(f"causeOfLeak: unrecognised value '{v}'")

    # memberSince is primary; manualStart is the fallback
    member_since_raw = row.get("memberSince") or row.get("manualStart")

    # Accept either column name for the referral source field
    referral_raw = row.get("referralSource") or row.get("howDidYouHearAboutUs")
    referral_list = _parse_pipe_list(referral_raw) or None

    member_data = {
        "age_band": to_age_band(row.get("dateOfBirth")),
        "gender": normalise_gender(row.get("gender")),
        "country": (row.get("country") or "").strip(),
        "region": (row.get("countyRegionStateProvince") or "").strip() or None,
        "outward_code": to_outward_code(row.get("postcodeZipCode")),
        "member_since_year": to_membership_year(member_since_raw),
        "referral_source": referral_list,
    }

    health_data = {
        "statuses": statuses,
        "leak_types": leak_types,
        "causes": causes,
    }

    return member_data, health_data, warnings


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def run_import(
    csv_bytes: bytes,
    source_filename: str,
    imported_by: str,
    db: AsyncSession,
) -> PipelineResult:
    """
    Run the full membership import pipeline.

    Does NOT commit the database transaction. The caller must call
    ``await db.commit()`` on success, or let the session roll back on failure.

    Args:
        csv_bytes:        Raw CSV file bytes from the upload
        source_filename:  Original filename, written to the audit log
        imported_by:      Entra ID object ID of the admin initiating the import
        db:               Async database session (within an open transaction)

    Returns:
        PipelineResult with batch counts and rejection log

    Raises:
        PipelineHalt: Schema validation failed, PII detected in a transformed
                      record, or key unavailable. No data has been committed.
    """
    from pipeline.key_vault import get_pseudonymisation_key

    # Step 5a: fetch key once at batch start — held in memory only
    key: str | None = await get_pseudonymisation_key()

    try:
        # ── Steps 1+2: Parse headers and schema validation ────────────────────
        text = csv_bytes.decode("utf-8-sig")  # strip optional BOM
        reader = csv.DictReader(io.StringIO(text))

        if not reader.fieldnames:
            raise PipelineHalt("CSV has no headers — cannot proceed.")

        missing_cols = REQUIRED_COLUMNS - frozenset(reader.fieldnames)
        if missing_cols:
            raise PipelineHalt(
                f"Schema validation failed — missing required columns: {sorted(missing_cols)}"
            )

        rows = list(reader)
        total_records = len(rows)

        # ── Step 2: Geographic filter ─────────────────────────────────────────
        in_scope: list[dict] = []
        geo_skipped = 0
        for row in rows:
            if is_in_scope(row.get("country")):
                in_scope.append(row)
            else:
                geo_skipped += 1

        # ── Steps 3–5: Per-record validation, transform, PII check ───────────
        rejection_log: list[RejectionEntry] = []
        processed: list[tuple[str, dict, dict]] = []  # (pseudo_id, member_data, health_data)

        for row in in_scope:
            record_id = str(row.get("id") or "").strip()
            if not record_id:
                rejection_log.append(
                    RejectionEntry(record_id="unknown", reason="missing_member_id")
                )
                continue

            pseudo_id = compute_pseudo_id(record_id, key)
            member_data, health_data, _warnings = _transform_record(row)

            # Belt-and-braces PII check — halts entire import if triggered.
            # The allowlist transform should prevent this; the check guards
            # against future bugs that might accidentally pass PII through.
            pii_violations = check_for_pii(member_data)
            if pii_violations:
                raise PipelineHalt(
                    f"PII detected in transformed record (id={record_id}): {pii_violations}"
                )

            processed.append((pseudo_id, member_data, health_data))

        rejected_count = len(rejection_log)
        skipped_count = geo_skipped

        # ── Step 6: Upsert ────────────────────────────────────────────────────
        batch_id = uuid.uuid4()

        await db.execute(
            insert(ImportBatch).values(
                batch_id=batch_id,
                imported_by=imported_by,
                source_filename=source_filename,
                total_records=total_records,
                imported_records=0,      # updated with final count at end
                skipped_records=skipped_count + rejected_count,
                rejected_records=rejected_count,
            )
        )

        # Load erasure register once — fast set membership check per record
        erased_result = await db.execute(select(ErasureRegister.pseudo_id))
        erased_ids: frozenset[str] = frozenset(erased_result.scalars().all())

        imported_count = 0

        for pseudo_id, member_data, health_data in processed:
            # Erasure register check — skip silently, log reason
            if pseudo_id in erased_ids:
                skipped_count += 1
                rejection_log.append(RejectionEntry(
                    record_id=pseudo_id,
                    reason="subject_erased",
                    detail="pseudo_id found in erasure_register — record not re-imported",
                ))
                continue

            # Upsert member row.
            # On conflict: update all mutable fields, leave first_seen_batch unchanged.
            await db.execute(
                pg_insert(Member).values(
                    pseudo_id=pseudo_id,
                    first_seen_batch=batch_id,
                    last_updated_batch=batch_id,
                    **member_data,
                ).on_conflict_do_update(
                    index_elements=["pseudo_id"],
                    set_={
                        "age_band": member_data["age_band"],
                        "gender": member_data["gender"],
                        "country": member_data["country"],
                        "region": member_data["region"],
                        "outward_code": member_data["outward_code"],
                        "member_since_year": member_data["member_since_year"],
                        "referral_source": member_data["referral_source"],
                        "last_updated_batch": batch_id,
                        # first_seen_batch is intentionally NOT updated on conflict
                    }
                )
            )

            # Child tables: delete existing rows and re-insert to reflect
            # current import state. This correctly handles additions, removals,
            # and no-change cases within the same transaction.
            await db.execute(
                delete(MemberStatus).where(MemberStatus.pseudo_id == pseudo_id)
            )
            if health_data["statuses"]:
                await db.execute(
                    insert(MemberStatus).values([
                        {
                            "id": uuid.uuid4(),
                            "pseudo_id": pseudo_id,
                            "status_value": s,
                            "import_batch_id": batch_id,
                        }
                        for s in health_data["statuses"]
                    ])
                )

            await db.execute(
                delete(CSFLeakType).where(CSFLeakType.pseudo_id == pseudo_id)
            )
            if health_data["leak_types"]:
                await db.execute(
                    insert(CSFLeakType).values([
                        {
                            "id": uuid.uuid4(),
                            "pseudo_id": pseudo_id,
                            "leak_type": lt,
                            "import_batch_id": batch_id,
                        }
                        for lt in health_data["leak_types"]
                    ])
                )

            await db.execute(
                delete(CauseOfLeak).where(CauseOfLeak.pseudo_id == pseudo_id)
            )
            if health_data["causes"]:
                await db.execute(
                    insert(CauseOfLeak).values([
                        {
                            "id": uuid.uuid4(),
                            "pseudo_id": pseudo_id,
                            "cause": c,
                            "import_batch_id": batch_id,
                        }
                        for c in health_data["causes"]
                    ])
                )

            imported_count += 1

        # Update batch record with final counts
        await db.execute(
            update(ImportBatch)
            .where(ImportBatch.batch_id == batch_id)
            .values(
                imported_records=imported_count,
                skipped_records=skipped_count,
                rejected_records=rejected_count,
            )
        )

        return PipelineResult(
            batch_id=batch_id,
            total_records=total_records,
            imported_records=imported_count,
            skipped_records=skipped_count,
            rejected_records=rejected_count,
            rejection_log=rejection_log,
        )

    finally:
        # Remove key reference. Python strings are immutable so we cannot zero
        # the bytes in place, but removing the reference allows GC to collect
        # it. The key is never written to disk, logs, or any persistent store.
        key = None
