"""
Report 1 — Cohort Overview.

Whole-cohort snapshot: size, status composition, geographic spread,
and data completeness. No filters — always represents the full cohort.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import MIN_COHORT_SIZE, SUFFERER_STATUSES_SQL, cell, pct


async def run(db: AsyncSession) -> dict:
    min_c = MIN_COHORT_SIZE

    # ── Total cohort size ─────────────────────────────────────────────────────
    total: int = (await db.execute(text("SELECT COUNT(*) FROM members"))).scalar()

    # ── Status breakdown ──────────────────────────────────────────────────────
    status_rows = (await db.execute(text("""
        SELECT status_value, COUNT(DISTINCT pseudo_id) AS cnt
        FROM member_statuses
        GROUP BY status_value
        ORDER BY cnt DESC
    """))).fetchall()
    status_counts: dict[str, int] = {r.status_value: r.cnt for r in status_rows}

    diagnosed      = status_counts.get("csfLeakSuffererDiagnosed", 0)
    suspected      = status_counts.get("csfLeakSuffererSuspected", 0)
    former         = status_counts.get("formerCsfLeakSufferer", 0)
    total_sufferers = diagnosed + suspected + former
    active_sufferers = diagnosed + suspected
    supporters     = (
        status_counts.get("familyFriendOfSufferer", 0)
        + status_counts.get("medicalProfessional", 0)
    )

    # ── Country breakdown (k≥10) ──────────────────────────────────────────────
    country_rows = (await db.execute(text("""
        SELECT country, COUNT(*) AS cnt
        FROM members
        GROUP BY country
        HAVING COUNT(*) >= :min_c
        ORDER BY cnt DESC
    """), {"min_c": min_c})).fetchall()

    shown_total = sum(r.cnt for r in country_rows)
    suppressed_member_count = total - shown_total

    # ── Data completeness ─────────────────────────────────────────────────────
    comp = (await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE gender IS NOT NULL)   AS has_gender,
            COUNT(*) FILTER (WHERE age_band IS NOT NULL) AS has_age_band
        FROM members
    """))).fetchone()

    has_leak_type: int = (await db.execute(text("""
        SELECT COUNT(DISTINCT pseudo_id)
        FROM csf_leak_types
        WHERE leak_type != 'notRelevant'
    """))).scalar()

    has_cause: int = (await db.execute(text("""
        SELECT COUNT(DISTINCT pseudo_id) FROM causes_of_leak
    """))).scalar()

    # ── Assemble ──────────────────────────────────────────────────────────────
    return {
        "total_members": total,
        "status_breakdown": [
            {
                "status": sv,
                "count": cnt,
                "pct_of_total": pct(cnt, total),
            }
            for sv, cnt in status_counts.items()
        ],
        "sufferer_summary": {
            "total_sufferers": total_sufferers,
            "pct_of_total": pct(total_sufferers, total),
            "active_sufferers": {
                "count": active_sufferers,
                "pct_of_sufferers": pct(active_sufferers, total_sufferers),
            },
            "diagnosed": {
                "count": diagnosed,
                "pct_of_sufferers": pct(diagnosed, total_sufferers),
                "pct_of_active": pct(diagnosed, active_sufferers),
            },
            "suspected": {
                "count": suspected,
                "pct_of_sufferers": pct(suspected, total_sufferers),
            },
            "former": {
                "count": former,
                "pct_of_sufferers": pct(former, total_sufferers),
            },
        },
        "supporter_summary": {
            "total_supporters": supporters,
            "pct_of_total": pct(supporters, total),
        },
        "country_breakdown": {
            "shown": [
                {"country": r.country, "count": r.cnt, "pct_of_total": pct(r.cnt, total)}
                for r in country_rows
            ],
            "suppressed_member_count": suppressed_member_count,
            "suppression_note": (
                f"Countries with fewer than {min_c} members are not shown individually. "
                f"{suppressed_member_count} member(s) are in suppressed countries."
            ),
        },
        "data_completeness": {
            "denominator": total,
            "denominator_note": (
                "Non-sufferer members (family/friend, medical professional) are expected "
                "to have no leak type or cause of leak."
            ),
            "gender":        {"count": comp.has_gender,   "pct": pct(comp.has_gender, total)},
            "age_band":      {"count": comp.has_age_band, "pct": pct(comp.has_age_band, total)},
            "leak_type":     {"count": has_leak_type,     "pct": pct(has_leak_type, total)},
            "cause_of_leak": {"count": has_cause,         "pct": pct(has_cause, total)},
        },
    }
