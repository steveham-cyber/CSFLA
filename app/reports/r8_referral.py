"""
Report 8 — Referral Source Analysis.

How members heard about the charity, from the referral_source array field.
Null referral_source values are counted separately (not collapsed into 'unknown').
Cross-tabulated with membership year.
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    MIN_COHORT_SIZE,
    cell,
    pct,
    member_filter_parts,
    where_clause,
)


async def run(
    db: AsyncSession,
    year_from: int | None = None,
    year_to: int | None = None,
    country: str | None = None,
) -> dict:
    conditions, params = member_filter_parts(
        country=country,
        year_from=year_from,
        year_to=year_to,
    )
    params["min_c"] = MIN_COHORT_SIZE

    # ── Members with NULL referral_source ─────────────────────────────────────
    null_conds = conditions + ["m.referral_source IS NULL"]
    null_where = where_clause(null_conds, prefix="WHERE")
    null_count: int = (await db.execute(text(f"""
        SELECT COUNT(*) FROM members m
        {null_where}
    """), params)).scalar()

    # ── Primary breakdown: source counts (LEFT JOIN LATERAL) ──────────────────
    # Using LEFT JOIN LATERAL so members with no referral entries are not dropped;
    # we separately count NULLs above.
    ref_conds = conditions + ["m.referral_source IS NOT NULL"]
    ref_where = where_clause(ref_conds, prefix="WHERE")
    source_rows = (await db.execute(text(f"""
        SELECT src.source, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        CROSS JOIN LATERAL unnest(m.referral_source) AS src(source)
        {ref_where}
        GROUP BY src.source
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_c
        ORDER BY cnt DESC
    """), params)).fetchall()

    total_with_source = (await db.execute(text(f"""
        SELECT COUNT(DISTINCT m.pseudo_id)
        FROM members m
        CROSS JOIN LATERAL unnest(m.referral_source) AS src(source)
        {ref_where}
    """), {k: v for k, v in params.items() if k != "min_c"})).scalar()

    primary = [
        {
            "source": r.source,
            "count": r.cnt,
            "pct_of_members_with_source": pct(r.cnt, total_with_source),
        }
        for r in source_rows
    ]

    # ── Cross-tab: source × member_since_year ─────────────────────────────────
    year_conds = conditions + ["m.referral_source IS NOT NULL", "m.member_since_year IS NOT NULL"]
    year_where = where_clause(year_conds, prefix="WHERE")
    year_rows = (await db.execute(text(f"""
        SELECT src.source, m.member_since_year AS yr, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        CROSS JOIN LATERAL unnest(m.referral_source) AS src(source)
        {year_where}
        GROUP BY src.source, m.member_since_year
        ORDER BY m.member_since_year, cnt DESC
    """), {k: v for k, v in params.items() if k != "min_c"})).fetchall()

    # Collect all years and all sources seen in the year cross-tab
    year_pivot: dict[int, dict[str, int]] = defaultdict(dict)
    sources_in_xtab: set[str] = set()
    for r in year_rows:
        year_pivot[r.yr][r.source] = r.cnt
        sources_in_xtab.add(r.source)

    # Only include top sources (those that appear in primary breakdown with >= min_c)
    shown_sources = {r.source for r in source_rows}

    by_year = []
    for yr in sorted(year_pivot.keys()):
        row: dict = {"year": yr}
        for source in sorted(shown_sources):
            row[source] = cell(year_pivot[yr].get(source, 0))
        by_year.append(row)

    return {
        "filters_applied": {
            "year_from": year_from,
            "year_to": year_to,
            "country": country,
        },
        "primary": {
            "total_members_with_source": total_with_source,
            "total_members_null_source": null_count,
            "null_note": (
                "Members with no referral_source recorded are counted separately. "
                "Null values are not collapsed into any source category."
            ),
            "denominator_note": (
                f"pct_of_members_with_source = count ÷ members with at least one referral source. "
                f"Sources with fewer than {MIN_COHORT_SIZE} members are suppressed."
            ),
            "breakdown": primary,
        },
        "by_year": by_year,
        "shown_sources": sorted(shown_sources),
    }
