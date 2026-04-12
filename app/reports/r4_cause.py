"""
Report 4 — Cause of Leak Analysis.

Cause distribution for the sufferer cohort, grouped into clinically meaningful
categories. Cross-tabulated with leak type, status, and demographics.

Multi-value note: a member with two causes (e.g. EDS + lumbar puncture) appears
in both cause rows and in both cause groups. Counts are member counts per cause,
not unique-member totals. See denominator_note in the response.
"""

from __future__ import annotations
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from reports import (
    CAUSE_GROUP_CASE_EXPR,
    CAUSE_GROUPS,
    CAUSE_GROUP_ORDER,
    CAUSE_TO_GROUP,
    LEAK_TYPE_ORDER,
    SUFFERER_STATUSES_SQL,
    cell,
    pct,
    member_filter_parts,
    where_clause,
)


async def run(
    db: AsyncSession,
    cause_group: str | None = None,
    individual_cause: str | None = None,
    leak_type: str | None = None,
    diagnostic_status: str | None = None,
    country: str | None = None,
    gender: str | None = None,
    age_band: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    conditions, params = member_filter_parts(country, gender, age_band, year_from, year_to)

    # Sufferer scope always applied
    base_conditions: list[str] = [f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + conditions

    if diagnostic_status:
        base_conditions.append("ms.status_value = :diagnostic_status")
        params["diagnostic_status"] = diagnostic_status

    if leak_type:
        base_conditions.append("lt.leak_type = :leak_type")
        params["leak_type"] = leak_type

    if individual_cause:
        base_conditions.append("c.cause = :individual_cause")
        params["individual_cause"] = individual_cause
    elif cause_group and cause_group in CAUSE_GROUPS:
        # Embed controlled-vocabulary group causes as SQL literals (safe)
        group_causes_sql = ", ".join(f"'{v}'" for v in sorted(CAUSE_GROUPS[cause_group]))
        base_conditions.append(f"c.cause IN ({group_causes_sql})")

    # Determine whether we need the leak_types join in the base query
    needs_lt_join = leak_type is not None

    def _from_clause(include_lt: bool = False) -> str:
        lt_join = "JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id" if include_lt else ""
        return f"""
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {lt_join}
        """

    # ── Cause group counts ────────────────────────────────────────────────────
    group_where = where_clause(base_conditions)
    group_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        {_from_clause(needs_lt_join)}
        {group_where}
        GROUP BY cause_group
    """), params)).fetchall()

    group_counts: dict[str, int] = {r.cause_group: r.cnt for r in group_rows}
    total_members_with_cause: int = (await db.execute(text(f"""
        SELECT COUNT(DISTINCT m.pseudo_id)
        {_from_clause(needs_lt_join)}
        {group_where}
    """), params)).scalar()

    # ── Individual cause counts ───────────────────────────────────────────────
    cause_rows = (await db.execute(text(f"""
        SELECT c.cause, COUNT(DISTINCT m.pseudo_id) AS cnt
        {_from_clause(needs_lt_join)}
        {group_where}
        GROUP BY c.cause
        ORDER BY cnt DESC
    """), params)).fetchall()

    individual_counts: dict[str, int] = {r.cause: r.cnt for r in cause_rows}

    # Assemble grouped + drilldown structure
    cause_groups_result = []
    for group_name in CAUSE_GROUP_ORDER:
        group_cnt = group_counts.get(group_name, 0)
        group_causes = CAUSE_GROUPS.get(group_name, frozenset())
        drilldown = [
            {
                "cause": cause,
                "count": individual_counts.get(cause, 0),
                "pct_of_group": pct(individual_counts.get(cause, 0), group_cnt),
            }
            for cause in sorted(group_causes)
            if individual_counts.get(cause, 0) > 0
        ]
        cause_groups_result.append({
            "cause_group": group_name,
            "count": group_cnt,
            "pct_of_total_with_cause": pct(group_cnt, total_members_with_cause),
            "individual_causes": drilldown,
        })

    # ── Cross-tab: cause group × leak type ────────────────────────────────────
    # Always join csf_leak_types for this cross-tab
    lt_conditions = base_conditions + ["lt.leak_type != 'notRelevant'"]
    lt_where = where_clause(lt_conditions)
    lt_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, lt.leak_type,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {lt_where}
        GROUP BY cause_group, lt.leak_type
    """), params)).fetchall()

    lt_pivot: dict[str, dict[str, int]] = defaultdict(dict)
    for r in lt_rows:
        lt_pivot[r.cause_group][r.leak_type] = r.cnt

    crosstab_leak_type = []
    for group_name in CAUSE_GROUP_ORDER:
        row: dict = {"cause_group": group_name}
        row_total = 0
        for lt in LEAK_TYPE_ORDER:
            cnt = lt_pivot.get(group_name, {}).get(lt, 0)
            row[lt] = cell(cnt)
            row_total += cnt
        row["total"] = cell(row_total)
        crosstab_leak_type.append(row)

    # ── Cross-tab helper: cause group × demographic dimension ─────────────────
    async def _group_xtab(dimension_col: str) -> list[dict]:
        xtab_conds = base_conditions + [f"m.{dimension_col} IS NOT NULL"]
        xtab_where = where_clause(xtab_conds)
        rows = (await db.execute(text(f"""
            SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, m.{dimension_col} AS dim_val,
                   COUNT(DISTINCT m.pseudo_id) AS cnt
            {_from_clause(needs_lt_join)}
            {xtab_where}
            GROUP BY cause_group, m.{dimension_col}
        """), params)).fetchall()

        pivot: dict[str, dict[str, int]] = defaultdict(dict)
        totals: dict[str, int] = defaultdict(int)
        for r in rows:
            pivot[r.dim_val][r.cause_group] = r.cnt
            totals[r.dim_val] += r.cnt

        result = []
        for dim_val in sorted(pivot.keys(), key=str):
            row: dict = {"value": dim_val, "total": cell(totals[dim_val])}
            for g in CAUSE_GROUP_ORDER:
                row[g] = cell(pivot[dim_val].get(g, 0))
            result.append(row)
        return result

    by_status_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, ms.status_value AS dim_val,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        {_from_clause(needs_lt_join)}
        {group_where}
        GROUP BY cause_group, ms.status_value
    """), params)).fetchall()

    status_pivot: dict[str, dict[str, int]] = defaultdict(dict)
    for r in by_status_rows:
        status_pivot[r.dim_val][r.cause_group] = r.cnt

    by_status = []
    for dim_val in sorted(status_pivot.keys(), key=str):
        row: dict = {"value": dim_val}
        row_total = 0
        for g in CAUSE_GROUP_ORDER:
            cnt = status_pivot[dim_val].get(g, 0)
            row[g] = cell(cnt)
            row_total += cnt
        row["total"] = cell(row_total)
        by_status.append(row)

    by_age_band = await _group_xtab("age_band")
    by_gender   = await _group_xtab("gender")
    by_country  = await _group_xtab("country")
    by_year     = await _group_xtab("member_since_year")

    return {
        "filters_applied": {
            "cause_group": cause_group,
            "individual_cause": individual_cause,
            "leak_type": leak_type,
            "diagnostic_status": diagnostic_status,
            "country": country,
            "gender": gender,
            "age_band": age_band,
            "year_from": year_from,
            "year_to": year_to,
        },
        "primary": {
            "total_members_with_cause": total_members_with_cause,
            "denominator_note": (
                "A member with two causes appears in both cause rows and both cause groups. "
                "Cause group counts are distinct members with at least one cause in that group. "
                "Group counts do not sum to total_members_with_cause."
            ),
            "cause_groups": cause_groups_result,
        },
        "crosstab_leak_type": {
            "matrix": crosstab_leak_type,
            "denominator_note": (
                "Each cell is the count of distinct members with that cause group AND that leak type. "
                "Row totals may exceed cause group counts due to members with multiple leak types."
            ),
        },
        "by_status":   by_status,
        "by_age_band": by_age_band,
        "by_gender":   by_gender,
        "by_country":  by_country,
        "by_year":     by_year,
    }
