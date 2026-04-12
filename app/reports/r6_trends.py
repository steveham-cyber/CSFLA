"""
Report 6 — Membership Growth and Cohort Trends.

Time series metrics across member_since_year for the sufferer cohort.
Minimum 3-year window enforced before breakdown charts are returned.

IMPORTANT: member_since_year reflects when someone joined the charity, not
when they developed or were diagnosed. Growth reflects charity awareness, not
condition prevalence. This must be stated clearly in the UI.
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    CAUSE_GROUP_CASE_EXPR,
    CAUSE_GROUPS,
    CAUSE_GROUP_ORDER,
    LEAK_TYPE_ORDER,
    SUFFERER_STATUSES_SQL,
    MIN_COHORT_SIZE,
    cell,
    pct,
    member_filter_parts,
    where_clause,
)

_MIN_YEAR_RANGE = 3

_UK_COUNTRIES_SQL = "'England', 'Scotland', 'Wales', 'Northern Ireland'"


async def run(
    db: AsyncSession,
    diagnostic_status: str | None = None,
    country: str | None = None,
    leak_type: str | None = None,
    cause_group: str | None = None,
) -> dict:
    params: dict = {}
    base_conditions: list[str] = [
        f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
        "m.member_since_year IS NOT NULL",
    ]

    if diagnostic_status:
        base_conditions.append("ms.status_value = :diagnostic_status")
        params["diagnostic_status"] = diagnostic_status
    if country:
        base_conditions.append("m.country = :country")
        params["country"] = country
    if leak_type:
        params["leak_type"] = leak_type

    # ── New sufferers per year ────────────────────────────────────────────────
    year_where = where_clause(base_conditions)
    year_rows = (await db.execute(text(f"""
        SELECT m.member_since_year AS yr, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {year_where}
        GROUP BY m.member_since_year
        ORDER BY m.member_since_year
    """), params)).fetchall()

    years = [r.yr for r in year_rows]
    year_counts: dict[int, int] = {r.yr: r.cnt for r in year_rows}
    year_range = len(years)
    has_enough_years = year_range >= _MIN_YEAR_RANGE

    # Cumulative cohort (all members, not just sufferers)
    cumulative_rows = (await db.execute(text("""
        SELECT member_since_year AS yr, COUNT(*) AS cnt
        FROM members
        WHERE member_since_year IS NOT NULL
        GROUP BY member_since_year
        ORDER BY member_since_year
    """))).fetchall()
    cumulative_counts: dict[int, int] = {r.yr: r.cnt for r in cumulative_rows}
    all_years = sorted(set(years) | set(cumulative_counts.keys()))
    running = 0
    cumulative_by_year: dict[int, int] = {}
    for yr in all_years:
        running += cumulative_counts.get(yr, 0)
        cumulative_by_year[yr] = running

    # ── Diagnosed % per year ──────────────────────────────────────────────────
    diag_conds = [f"ms.status_value IN ('csfLeakSuffererDiagnosed','csfLeakSuffererSuspected')",
                  "m.member_since_year IS NOT NULL"]
    if country:
        diag_conds.append("m.country = :country")
    diag_where = where_clause(diag_conds)
    diag_rows = (await db.execute(text(f"""
        SELECT m.member_since_year AS yr, ms.status_value, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {diag_where}
        GROUP BY m.member_since_year, ms.status_value
    """), {k: v for k, v in params.items() if k != "diagnostic_status"})).fetchall()

    diag_by_year: dict[int, int] = defaultdict(int)
    suspected_by_year: dict[int, int] = defaultdict(int)
    for r in diag_rows:
        if r.status_value == "csfLeakSuffererDiagnosed":
            diag_by_year[r.yr] += r.cnt
        elif r.status_value == "csfLeakSuffererSuspected":
            suspected_by_year[r.yr] += r.cnt

    # ── Cause group % per year ────────────────────────────────────────────────
    cause_year_conds = [f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
                        "m.member_since_year IS NOT NULL"]
    if country:
        cause_year_conds.append("m.country = :country")
    if cause_group and cause_group in CAUSE_GROUPS:
        group_causes_sql = ", ".join(f"'{v}'" for v in sorted(CAUSE_GROUPS[cause_group]))
        cause_year_conds.append(f"c.cause IN ({group_causes_sql})")
    cause_year_where = where_clause(cause_year_conds)
    cause_year_rows = (await db.execute(text(f"""
        SELECT m.member_since_year AS yr, ({CAUSE_GROUP_CASE_EXPR}) AS cause_group,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {cause_year_where}
        GROUP BY m.member_since_year, cause_group
        ORDER BY m.member_since_year
    """), {k: v for k, v in params.items() if k != "diagnostic_status"})).fetchall()

    cause_by_year: dict[int, dict[str, int]] = defaultdict(dict)
    for r in cause_year_rows:
        cause_by_year[r.yr][r.cause_group] = r.cnt

    # ── Leak type % per year ──────────────────────────────────────────────────
    lt_year_conds = [f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
                     "m.member_since_year IS NOT NULL",
                     "lt.leak_type != 'notRelevant'"]
    if country:
        lt_year_conds.append("m.country = :country")
    if leak_type:
        lt_year_conds.append("lt.leak_type = :leak_type")
    lt_year_where = where_clause(lt_year_conds)
    lt_year_rows = (await db.execute(text(f"""
        SELECT m.member_since_year AS yr, lt.leak_type, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {lt_year_where}
        GROUP BY m.member_since_year, lt.leak_type
        ORDER BY m.member_since_year
    """), params)).fetchall()

    lt_by_year: dict[int, dict[str, int]] = defaultdict(dict)
    for r in lt_year_rows:
        lt_by_year[r.yr][r.leak_type] = r.cnt

    # ── Geographic origin per year (UK vs Europe) ─────────────────────────────
    geo_year_conds = [f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
                      "m.member_since_year IS NOT NULL"]
    geo_year_where = where_clause(geo_year_conds)
    geo_year_rows = (await db.execute(text(f"""
        SELECT m.member_since_year AS yr,
               CASE WHEN m.country IN ({_UK_COUNTRIES_SQL}) THEN 'UK' ELSE 'Europe' END AS geo,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {geo_year_where}
        GROUP BY m.member_since_year, geo
        ORDER BY m.member_since_year
    """), {})).fetchall()

    geo_by_year: dict[int, dict[str, int]] = defaultdict(dict)
    for r in geo_year_rows:
        geo_by_year[r.yr][r.geo] = r.cnt

    # ── Assemble per-year rows ────────────────────────────────────────────────
    year_series = []
    for yr in years:
        suf_cnt = year_counts[yr]
        d_cnt = diag_by_year.get(yr, 0)
        s_cnt = suspected_by_year.get(yr, 0)
        active_total = d_cnt + s_cnt

        year_entry: dict = {
            "year": yr,
            "new_sufferers": suf_cnt,
            "cumulative_members": cumulative_by_year.get(yr),
            "diagnosed_pct_of_active": pct(d_cnt, active_total),
            # Cause/type breakdowns suppressed if year has < 10 sufferers
            "cause_breakdown_suppressed": suf_cnt < MIN_COHORT_SIZE,
            "type_breakdown_suppressed": suf_cnt < MIN_COHORT_SIZE,
        }

        if suf_cnt >= MIN_COHORT_SIZE:
            cg_year = cause_by_year.get(yr, {})
            year_entry["cause_breakdown"] = {
                g: cell(cg_year.get(g, 0)) for g in CAUSE_GROUP_ORDER
            }
            lt_year = lt_by_year.get(yr, {})
            year_entry["leak_type_breakdown"] = {
                lt: cell(lt_year.get(lt, 0)) for lt in LEAK_TYPE_ORDER
            }

        geo = geo_by_year.get(yr, {})
        year_entry["geographic_origin"] = {
            "UK": geo.get("UK", 0),
            "Europe": geo.get("Europe", 0),
        }

        year_series.append(year_entry)

    return {
        "filters_applied": {
            "diagnostic_status": diagnostic_status,
            "country": country,
            "leak_type": leak_type,
            "cause_group": cause_group,
        },
        "year_range": {
            "first_year": years[0] if years else None,
            "last_year":  years[-1] if years else None,
            "distinct_years": year_range,
        },
        "trend_charts_available": has_enough_years,
        "trend_charts_note": (
            None if has_enough_years
            else f"Trend charts require at least {_MIN_YEAR_RANGE} years of data."
        ),
        "scope_note": (
            "member_since_year reflects when someone joined the charity, not when they developed "
            "or were diagnosed with a CSF leak. Growth reflects awareness of the charity."
        ),
        "by_year": year_series,
    }
