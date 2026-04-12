"""
Report 3 — CSF Leak Type Distribution.

Leak type breakdown for sufferer cohort, cross-tabulated with demographics.
Scope: sufferers only; notRelevant leak type excluded throughout.
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    SUFFERER_STATUSES_SQL,
    LEAK_TYPE_ORDER,
    cell,
    pct,
    member_filter_parts,
    where_clause,
)


async def run(
    db: AsyncSession,
    diagnostic_status: str | None = None,
    country: str | None = None,
    gender: str | None = None,
    age_band: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    conditions, params = member_filter_parts(country, gender, age_band, year_from, year_to)

    # Sufferer scope + notRelevant exclusion always applied
    base_conditions = [
        f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
        "lt.leak_type != 'notRelevant'",
    ] + conditions

    if diagnostic_status:
        base_conditions.append("ms.status_value = :diagnostic_status")
        params["diagnostic_status"] = diagnostic_status

    # ── Primary leak type counts ──────────────────────────────────────────────
    primary_where = where_clause(base_conditions)
    primary_rows = (await db.execute(text(f"""
        SELECT lt.leak_type, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {primary_where}
        GROUP BY lt.leak_type
        ORDER BY cnt DESC
    """), params)).fetchall()

    total_with_type = sum(r.cnt for r in primary_rows)
    unknown_count   = next((r.cnt for r in primary_rows if r.leak_type == "unknown"), 0)
    known_total     = total_with_type - unknown_count

    primary = [
        {
            "leak_type": r.leak_type,
            "count": r.cnt,
            "pct_of_sufferers_with_type": pct(r.cnt, total_with_type),
        }
        for r in sorted(primary_rows, key=lambda r: LEAK_TYPE_ORDER.index(r.leak_type)
                        if r.leak_type in LEAK_TYPE_ORDER else 99)
    ]

    # ── Cross-tab helper (leak_type × dimension) ──────────────────────────────
    async def _xtab(dimension_col: str) -> list[dict]:
        xtab_conds = base_conditions + [f"m.{dimension_col} IS NOT NULL"]
        xtab_where = where_clause(xtab_conds)
        rows = (await db.execute(text(f"""
            SELECT lt.leak_type, m.{dimension_col} AS dim_val,
                   COUNT(DISTINCT m.pseudo_id) AS cnt
            FROM members m
            JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
            JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
            {xtab_where}
            GROUP BY lt.leak_type, m.{dimension_col}
        """), params)).fetchall()

        pivot: dict[str, dict[str, int]] = defaultdict(dict)
        totals: dict[str, int] = defaultdict(int)
        for r in rows:
            pivot[r.dim_val][r.leak_type] = r.cnt
            totals[r.dim_val] += r.cnt

        result = []
        for dim_val in sorted(pivot.keys(), key=str):
            row: dict = {"value": dim_val, "total": cell(totals[dim_val])}
            for lt, cnt in pivot[dim_val].items():
                row[lt] = cell(cnt)
            result.append(row)
        return result

    # ── Cross-tab: leak_type × diagnostic_status ──────────────────────────────
    # Slightly different: dimension is status, not a members column
    status_conds = [
        f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
        "lt.leak_type != 'notRelevant'",
    ] + conditions  # do NOT re-apply diagnostic_status filter here
    status_xtab_where = where_clause(status_conds)
    status_rows = (await db.execute(text(f"""
        SELECT lt.leak_type, ms.status_value AS dim_val,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {status_xtab_where}
        GROUP BY lt.leak_type, ms.status_value
    """), {k: v for k, v in params.items() if k != "diagnostic_status"})).fetchall()

    status_pivot: dict[str, dict[str, int]] = defaultdict(dict)
    status_totals: dict[str, int] = defaultdict(int)
    for r in status_rows:
        status_pivot[r.dim_val][r.leak_type] = r.cnt
        status_totals[r.dim_val] += r.cnt

    by_status = []
    for dim_val in sorted(status_pivot.keys(), key=str):
        row: dict = {"value": dim_val, "total": cell(status_totals[dim_val])}
        for lt, cnt in status_pivot[dim_val].items():
            row[lt] = cell(cnt)
        by_status.append(row)

    by_age_band = await _xtab("age_band")
    by_gender   = await _xtab("gender")
    by_country  = await _xtab("country")
    by_year     = await _xtab("member_since_year")

    return {
        "filters_applied": {
            "diagnostic_status": diagnostic_status,
            "country": country,
            "gender": gender,
            "age_band": age_band,
            "year_from": year_from,
            "year_to": year_to,
        },
        "primary": {
            "total_sufferers_with_type": total_with_type,
            "known_type_total": known_total,
            "unknown_rate_pct": pct(unknown_count, total_with_type),
            "denominator_note": (
                "pct_of_sufferers_with_type = count ÷ all sufferers with any leak type record "
                "(excludes notRelevant). A member may have multiple leak types."
            ),
            "breakdown": primary,
        },
        "by_status":   by_status,
        "by_age_band": by_age_band,
        "by_gender":   by_gender,
        "by_country":  by_country,
        "by_year":     by_year,
    }
