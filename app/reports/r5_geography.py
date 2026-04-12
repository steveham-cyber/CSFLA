"""
Report 5 — Geographic Distribution.

UK (country + region + outward code) and European country breakdowns.
Cross-tabulated with cause group and diagnostic status.
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    CAUSE_GROUP_CASE_EXPR,
    CAUSE_GROUPS,
    CAUSE_GROUP_ORDER,
    SUFFERER_STATUSES_SQL,
    MIN_COHORT_SIZE,
    cell,
    pct,
    where_clause,
)

_UK_COUNTRIES_SQL = "'England', 'Scotland', 'Wales', 'Northern Ireland'"


async def run(
    db: AsyncSession,
    country_group: str | None = None,   # "uk" | "europe" | None (both)
    diagnostic_status: str | None = None,
    leak_type: str | None = None,
    cause_group: str | None = None,
) -> dict:
    params: dict = {"min_c": MIN_COHORT_SIZE}
    # member_only_conditions: conditions on m.* only — safe to reuse in cross-tab
    # queries that independently join ms/lt/c without the base filter joins.
    member_only_conditions: list[str] = []
    base_conditions: list[str] = []

    if country_group == "uk":
        member_only_conditions.append(f"m.country IN ({_UK_COUNTRIES_SQL})")
    elif country_group == "europe":
        member_only_conditions.append(f"m.country NOT IN ({_UK_COUNTRIES_SQL})")

    base_conditions = list(member_only_conditions)

    if diagnostic_status:
        base_conditions.append("ms.status_value = :diagnostic_status")
        params["diagnostic_status"] = diagnostic_status

    if leak_type:
        base_conditions.append("lt.leak_type = :leak_type")
        params["leak_type"] = leak_type

    if cause_group and cause_group in CAUSE_GROUPS:
        group_causes_sql = ", ".join(f"'{v}'" for v in sorted(CAUSE_GROUPS[cause_group]))
        base_conditions.append(f"c.cause IN ({group_causes_sql})")

    # Determine which optional joins are needed
    needs_status = diagnostic_status is not None
    needs_lt     = leak_type is not None
    needs_cause  = cause_group is not None

    def _joins() -> str:
        parts = []
        if needs_status or needs_lt or needs_cause:
            # Always join statuses if any filter is active (for sufferer scope on cross-tabs)
            parts.append("LEFT JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id")
        if needs_lt:
            parts.append("LEFT JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id")
        if needs_cause:
            parts.append("LEFT JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id")
        return "\n        ".join(parts)

    base_where = where_clause(base_conditions)

    # ── UK: by country (England/Scotland/Wales/NI) ────────────────────────────
    uk_country_conds = base_conditions + [f"m.country IN ({_UK_COUNTRIES_SQL})"]
    uk_country_where = where_clause(uk_country_conds)
    uk_country_rows = (await db.execute(text(f"""
        SELECT m.country, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        {_joins()}
        {uk_country_where}
        GROUP BY m.country
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_c
        ORDER BY cnt DESC
    """), params)).fetchall()

    # ── UK: by region ─────────────────────────────────────────────────────────
    region_conds = base_conditions + [
        f"m.country IN ({_UK_COUNTRIES_SQL})",
        "m.region IS NOT NULL",
    ]
    region_where = where_clause(region_conds)
    region_rows = (await db.execute(text(f"""
        SELECT m.region, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        {_joins()}
        {region_where}
        GROUP BY m.region
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_c
        ORDER BY cnt DESC
    """), params)).fetchall()

    # ── UK: outward code density (k≥10, UK only) ──────────────────────────────
    oc_conds = base_conditions + [
        f"m.country IN ({_UK_COUNTRIES_SQL})",
        "m.outward_code IS NOT NULL",
    ]
    oc_where = where_clause(oc_conds)
    oc_rows = (await db.execute(text(f"""
        SELECT m.outward_code, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        {_joins()}
        {oc_where}
        GROUP BY m.outward_code
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_c
        ORDER BY cnt DESC
    """), params)).fetchall()

    # ── Europe: by country ────────────────────────────────────────────────────
    eu_conds = base_conditions + [f"m.country NOT IN ({_UK_COUNTRIES_SQL})"]
    eu_where = where_clause(eu_conds)
    eu_all_rows = (await db.execute(text(f"""
        SELECT m.country, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        {_joins()}
        {eu_where}
        GROUP BY m.country
        ORDER BY cnt DESC
    """), params)).fetchall()

    eu_shown = [r for r in eu_all_rows if r.cnt >= MIN_COHORT_SIZE]
    eu_other_total = sum(r.cnt for r in eu_all_rows if r.cnt < MIN_COHORT_SIZE)

    eu_breakdown = [
        {"country": r.country, "count": r.cnt, "pct": pct(r.cnt, sum(r2.cnt for r2 in eu_all_rows))}
        for r in eu_shown
    ]
    if eu_other_total > 0:
        eu_total = sum(r.cnt for r in eu_all_rows)
        eu_breakdown.append({
            "country": "Other Europe",
            "count": eu_other_total,
            "pct": pct(eu_other_total, eu_total),
            "note": f"Aggregate of countries with fewer than {MIN_COHORT_SIZE} members.",
        })

    # ── Cross-tab: cause group × country ─────────────────────────────────────
    cg_country_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, m.country,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {where_clause([f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + member_only_conditions)}
        GROUP BY cause_group, m.country
    """), {k: v for k, v in params.items() if k != "min_c"})).fetchall()

    cg_pivot: dict[str, dict[str, int]] = defaultdict(dict)
    all_countries_seen: set[str] = set()
    for r in cg_country_rows:
        cg_pivot[r.country][r.cause_group] = r.cnt
        all_countries_seen.add(r.country)

    crosstab_cause_by_country = []
    for country_val in sorted(all_countries_seen):
        row: dict = {"country": country_val}
        row_total = 0
        for g in CAUSE_GROUP_ORDER:
            cnt = cg_pivot[country_val].get(g, 0)
            row[g] = cell(cnt)
            row_total += cnt
        row["total"] = cell(row_total)
        crosstab_cause_by_country.append(row)

    # ── Cross-tab: diagnostic status × country ────────────────────────────────
    status_country_rows = (await db.execute(text(f"""
        SELECT ms.status_value, m.country, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {where_clause([f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + member_only_conditions)}
        GROUP BY ms.status_value, m.country
    """), {k: v for k, v in params.items() if k != "min_c"})).fetchall()

    sc_pivot: dict[str, dict[str, int]] = defaultdict(dict)
    sc_countries: set[str] = set()
    for r in status_country_rows:
        sc_pivot[r.country][r.status_value] = r.cnt
        sc_countries.add(r.country)

    crosstab_status_by_country = []
    for country_val in sorted(sc_countries):
        row: dict = {"country": country_val}
        row_total = 0
        for sv, cnt in sc_pivot[country_val].items():
            row[sv] = cell(cnt)
            row_total += cnt
        row["total"] = cell(row_total)
        crosstab_status_by_country.append(row)

    return {
        "filters_applied": {
            "country_group": country_group,
            "diagnostic_status": diagnostic_status,
            "leak_type": leak_type,
            "cause_group": cause_group,
        },
        "uk": {
            "by_country": [
                {"country": r.country, "count": r.cnt}
                for r in uk_country_rows
            ],
            "by_region": [
                {"region": r.region, "count": r.cnt}
                for r in region_rows
            ],
            "outward_code_density": {
                "data": [
                    {"outward_code": r.outward_code, "count": r.cnt}
                    for r in oc_rows
                ],
                "note": (
                    "Absolute counts only — no rates (population denominator unavailable). "
                    f"Outward codes with fewer than {MIN_COHORT_SIZE} members are suppressed."
                ),
            },
        },
        "europe": {
            "by_country": eu_breakdown,
            "note": (
                f"EEA countries with fewer than {MIN_COHORT_SIZE} members grouped as 'Other Europe'."
            ),
        },
        "crosstab_cause_by_country": crosstab_cause_by_country,
        "crosstab_status_by_country": crosstab_status_by_country,
    }
