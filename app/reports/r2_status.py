"""
Report 2 — Diagnostic Status Profile.

Sufferer status breakdown cross-tabulated with demographic dimensions.
Scope: sufferer statuses only (diagnosed, suspected, former).
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    MIN_COHORT_SIZE,
    SUFFERER_STATUSES_SQL,
    cell,
    pct,
    member_filter_parts,
    where_clause,
)


async def run(
    db: AsyncSession,
    country: str | None = None,
    gender: str | None = None,
    age_band: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    conditions, params = member_filter_parts(country, gender, age_band, year_from, year_to)
    # Sufferer scope always applied
    base_conditions = [f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + conditions

    # ── Primary status counts ─────────────────────────────────────────────────
    primary_where = where_clause(base_conditions)
    primary_rows = (await db.execute(text(f"""
        SELECT ms.status_value, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {primary_where}
        GROUP BY ms.status_value
        ORDER BY cnt DESC
    """), params)).fetchall()

    total_sufferers = sum(r.cnt for r in primary_rows)
    diagnosed = next((r.cnt for r in primary_rows if r.status_value == "csfLeakSuffererDiagnosed"), 0)
    suspected  = next((r.cnt for r in primary_rows if r.status_value == "csfLeakSuffererSuspected"), 0)

    primary = [
        {
            "status": r.status_value,
            "count": r.cnt,
            "pct_of_sufferers": pct(r.cnt, total_sufferers),
        }
        for r in primary_rows
    ]

    # ── Cross-tab helper ──────────────────────────────────────────────────────
    async def _xtab(dimension_col: str) -> list[dict]:
        """
        For each value of dimension_col, return per-status counts.
        Suppresses individual cells below MIN_COHORT_SIZE.
        Rows with null dimension values are excluded.
        """
        xtab_conds = base_conditions + [f"m.{dimension_col} IS NOT NULL"]
        xtab_where = where_clause(xtab_conds)
        rows = (await db.execute(text(f"""
            SELECT ms.status_value, m.{dimension_col} AS dim_val,
                   COUNT(DISTINCT m.pseudo_id) AS cnt
            FROM members m
            JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
            {xtab_where}
            GROUP BY ms.status_value, m.{dimension_col}
        """), params)).fetchall()

        pivot: dict[str, dict[str, int]] = defaultdict(dict)
        totals: dict[str, int] = defaultdict(int)
        for r in rows:
            pivot[r.dim_val][r.status_value] = r.cnt
            totals[r.dim_val] += r.cnt

        result = []
        for dim_val in sorted(pivot.keys(), key=str):
            row: dict = {"value": dim_val, "total": cell(totals[dim_val])}
            for sv, cnt in pivot[dim_val].items():
                row[sv] = cell(cnt)
            result.append(row)
        return result

    # ── Execute cross-tabs ────────────────────────────────────────────────────
    by_age_band = await _xtab("age_band")
    by_gender   = await _xtab("gender")
    by_country  = await _xtab("country")
    by_region   = await _xtab("region")
    by_year     = await _xtab("member_since_year")

    return {
        "filters_applied": {
            "country": country,
            "gender": gender,
            "age_band": age_band,
            "year_from": year_from,
            "year_to": year_to,
        },
        "primary": {
            "total_sufferers": total_sufferers,
            "pct_diagnosed_of_active": pct(diagnosed, diagnosed + suspected),
            "denominator_note": (
                "pct_diagnosed_of_active = diagnosed ÷ (diagnosed + suspected). "
                "Former sufferers excluded from this ratio."
            ),
            "breakdown": primary,
        },
        "by_age_band": by_age_band,
        "by_gender":   by_gender,
        "by_country":  by_country,
        "by_region":   by_region,
        "by_year":     by_year,
    }
