"""
Admin endpoints — admin role only.
"""

import csv
import io
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_admin
from auth.entra import CurrentUser
from db.connection import get_db
from db.models import ExportAudit

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


# ── Cause-group mapping ───────────────────────────────────────────────────────

_CAUSE_GROUP_CASES = """
CASE
  WHEN cause IN ('spinalSurgery','cranialSurgery','lumbarPuncture','epiduralAnaesthesia','spinalAnaesthesia','otherIatrogenicCause') THEN 'Iatrogenic'
  WHEN cause IN ('ehlersDanlosSyndrome','marfanSyndrome','otherHeritableDisorderOfConnectiveTissue') THEN 'Connective Tissue Disorder'
  WHEN cause IN ('idiopathicIntracranialHypertension') THEN 'IIH-Related / Cranial'
  WHEN cause IN ('boneSpur','cystTarlovPerineuralMeningeal','sihNoStructuralLesion') THEN 'Spontaneous / Structural (Spinal)'
  WHEN cause IN ('trauma') THEN 'Traumatic'
  WHEN cause IN ('other') THEN 'Other'
  ELSE 'Unknown / Not disclosed'
END
""".strip()

_SUPPRESSION_SQL = text(f"""
SELECT age_band, gender, country,
       CASE
         WHEN c.cause IN ('spinalSurgery','cranialSurgery','lumbarPuncture','epiduralAnaesthesia','spinalAnaesthesia','otherIatrogenicCause') THEN 'Iatrogenic'
         WHEN c.cause IN ('ehlersDanlosSyndrome','marfanSyndrome','otherHeritableDisorderOfConnectiveTissue') THEN 'Connective Tissue Disorder'
         WHEN c.cause IN ('idiopathicIntracranialHypertension') THEN 'IIH-Related / Cranial'
         WHEN c.cause IN ('boneSpur','cystTarlovPerineuralMeningeal','sihNoStructuralLesion') THEN 'Spontaneous / Structural (Spinal)'
         WHEN c.cause IN ('trauma') THEN 'Traumatic'
         WHEN c.cause IN ('other') THEN 'Other'
         ELSE 'Unknown / Not disclosed'
       END as cause_group,
       COUNT(DISTINCT m.pseudo_id) as combo_count
FROM members m
LEFT JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
GROUP BY age_band, gender, country, cause_group
HAVING COUNT(DISTINCT m.pseudo_id) < 10
""")

_MAIN_DATA_SQL = text("""
SELECT
    m.pseudo_id,
    m.age_band, m.gender, m.country, m.region, m.member_since_year,
    m.referral_source,
    ARRAY_AGG(DISTINCT ms.status_value) FILTER (WHERE ms.status_value IS NOT NULL) as statuses,
    ARRAY_AGG(DISTINCT lt.leak_type) FILTER (WHERE lt.leak_type IS NOT NULL) as leak_types,
    ARRAY_AGG(DISTINCT c.cause) FILTER (WHERE c.cause IS NOT NULL) as causes,
    CASE
      WHEN MAX(c.cause) IN ('spinalSurgery','cranialSurgery','lumbarPuncture','epiduralAnaesthesia','spinalAnaesthesia','otherIatrogenicCause') THEN 'Iatrogenic'
      WHEN MAX(c.cause) IN ('ehlersDanlosSyndrome','marfanSyndrome','otherHeritableDisorderOfConnectiveTissue') THEN 'Connective Tissue Disorder'
      WHEN MAX(c.cause) IN ('idiopathicIntracranialHypertension') THEN 'IIH-Related / Cranial'
      WHEN MAX(c.cause) IN ('boneSpur','cystTarlovPerineuralMeningeal','sihNoStructuralLesion') THEN 'Spontaneous / Structural (Spinal)'
      WHEN MAX(c.cause) IN ('trauma') THEN 'Traumatic'
      WHEN MAX(c.cause) IN ('other') THEN 'Other'
      ELSE 'Unknown / Not disclosed'
    END as primary_cause_group
FROM members m
LEFT JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
LEFT JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
LEFT JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
GROUP BY m.pseudo_id, m.age_band, m.gender, m.country, m.region, m.member_since_year, m.referral_source
ORDER BY m.country, m.age_band
""")


def _encode_array_csv(arr) -> str:
    """Encode a Postgres array value as pipe-separated string for CSV."""
    if not arr:
        return ""
    return "|".join(str(v) for v in arr)


def _encode_array_json(arr) -> list:
    """Encode a Postgres array value as a list for JSON/NDJSON."""
    if not arr:
        return []
    return list(arr)


@router.get("/export")
async def export_members(
    request: Request,
    fmt: str = Query(default="csv", alias="format", pattern="^(csv|json|ndjson)$"),
    acknowledged: bool = Query(default=False),
    user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all pseudonymised member records in CSV, JSON, or NDJSON format.

    - Requires admin role (REQ-EXP-01)
    - Requires acknowledged=true query param (REQ-EXP-11)
    - Rate-limited to 1 successful export per 24h per admin (REQ-EXP-12)
    - Suppresses combinations with fewer than 10 members (REQ-EXP-08)
    - Audit-logged on every call (REQ-EXP-03)
    - No pseudo_id or outward_code in output (REQ-EXP-05, REQ-EXP-06)
    """
    client_ip: str = request.client.host if request.client else "unknown"

    # REQ-EXP-11: Require explicit acknowledgement from the UI gate
    if not acknowledged:
        raise HTTPException(
            status_code=400,
            detail="acknowledged=true is required. Please confirm data handling obligations before downloading.",
        )

    # REQ-EXP-12: Rate limiting — one successful export per 24h per admin OID
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    rate_check = await db.execute(
        select(ExportAudit).where(
            ExportAudit.exported_by == user.id,
            ExportAudit.outcome == "success",
            ExportAudit.exported_at >= cutoff,
        ).limit(1)
    )
    if rate_check.scalar_one_or_none() is not None:
        # Write failure audit row for the rate-limit hit
        db.add(ExportAudit(
            exported_by=user.id,
            format=fmt,
            row_count=0,
            suppressed_count=0,
            client_ip=client_ip,
            outcome="failure",
            acknowledged=True,
        ))
        await db.commit()
        raise HTTPException(
            status_code=429,
            detail="Export limit reached. One export per 24-hour period is permitted.",
        )

    try:
        # REQ-EXP-08: Build suppression set
        suppression_result = await db.execute(_SUPPRESSION_SQL)
        suppressed_combos: set[tuple] = set()
        for row in suppression_result:
            suppressed_combos.add((row.age_band, row.gender, row.country, row.cause_group))

        # Fetch all members
        data_result = await db.execute(_MAIN_DATA_SQL)
        all_rows = data_result.fetchall()

        # Filter suppressed rows
        export_rows = []
        suppressed_count = 0
        for row in all_rows:
            combo = (row.age_band, row.gender, row.country, row.primary_cause_group)
            if combo in suppressed_combos:
                suppressed_count += 1
            else:
                export_rows.append(row)

        row_count = len(export_rows)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        exported_at_iso = datetime.utcnow().isoformat() + "Z"

        # REQ-EXP-03: Write audit row before generating response
        db.add(ExportAudit(
            exported_by=user.id,
            format=fmt,
            row_count=row_count,
            suppressed_count=suppressed_count,
            client_ip=client_ip,
            outcome="success",
            acknowledged=True,
        ))
        await db.commit()

    except HTTPException:
        raise
    except Exception:
        # Roll back the failed transaction before attempting the failure audit write
        await db.rollback()
        db.add(ExportAudit(
            exported_by=user.id,
            format=fmt,
            row_count=0,
            suppressed_count=0,
            client_ip=client_ip,
            outcome="failure",
            acknowledged=True,
        ))
        await db.commit()
        raise HTTPException(status_code=500, detail="An internal error occurred.")

    # ── Build response ────────────────────────────────────────────────────────

    if fmt == "csv":
        filename = f"csfla_members_{timestamp}Z.csv"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }

        def _csv_generator():
            output = io.StringIO()
            writer = csv.writer(output)
            # BOM for Excel compatibility
            yield "\ufeff"
            # Header row
            writer.writerow([
                "row_id", "age_band", "gender", "country", "region",
                "member_since_year", "referral_source",
                "statuses", "leak_types", "causes",
            ])
            yield output.getvalue()
            output.truncate(0)
            output.seek(0)
            for idx, row in enumerate(export_rows, start=1):
                writer.writerow([
                    idx,
                    row.age_band or "",
                    row.gender or "",
                    row.country or "",
                    row.region or "",
                    row.member_since_year or "",
                    _encode_array_csv(row.referral_source),
                    _encode_array_csv(row.statuses),
                    _encode_array_csv(row.leak_types),
                    _encode_array_csv(row.causes),
                ])
                yield output.getvalue()
                output.truncate(0)
                output.seek(0)

        return StreamingResponse(
            _csv_generator(),
            media_type="text/csv; charset=utf-8",
            headers=headers,
        )

    elif fmt == "json":
        records = [
            {
                "row_id": idx,
                "age_band": row.age_band,
                "gender": row.gender,
                "country": row.country,
                "region": row.region,
                "member_since_year": row.member_since_year,
                "referral_source": _encode_array_json(row.referral_source),
                "statuses": _encode_array_json(row.statuses),
                "leak_types": _encode_array_json(row.leak_types),
                "causes": _encode_array_json(row.causes),
            }
            for idx, row in enumerate(export_rows, start=1)
        ]
        return JSONResponse(content={
            "exported_at": exported_at_iso,
            "record_count": row_count,
            "suppressed_count": suppressed_count,
            "records": records,
        })

    else:  # ndjson
        def _ndjson_generator():
            for idx, row in enumerate(export_rows, start=1):
                record = {
                    "row_id": idx,
                    "age_band": row.age_band,
                    "gender": row.gender,
                    "country": row.country,
                    "region": row.region,
                    "member_since_year": row.member_since_year,
                    "referral_source": _encode_array_json(row.referral_source),
                    "statuses": _encode_array_json(row.statuses),
                    "leak_types": _encode_array_json(row.leak_types),
                    "causes": _encode_array_json(row.causes),
                }
                yield json.dumps(record) + "\n"

        return StreamingResponse(
            _ndjson_generator(),
            media_type="application/x-ndjson",
        )
