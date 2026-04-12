"""
Report 7 — Cause × Type Cross-Analysis.

Research-focused matrix: cause of leak (grouped + individual) × CSF leak type.
Includes chi-square test of independence.

Multi-value note: a member with two causes appears in two rows; a member with
two leak types appears in two columns. Cell counts are distinct members with
that (cause, leak_type) combination. See denominator_note in response.

Chi-square excludes 'Unknown / Not disclosed' cause group and 'unknown' leak
type, and flags cells where expected count < 5.
"""

from __future__ import annotations
from collections import defaultdict

import numpy as np
from scipy import stats
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


def _chi_square(
    matrix: dict[str, dict[str, int]],
) -> dict:
    """
    Chi-square test of independence on the cause_group × leak_type matrix.
    Excludes 'Unknown / Not disclosed' cause group and 'unknown' leak type.
    """
    test_groups = [g for g in CAUSE_GROUP_ORDER if g != "Unknown / Not disclosed"]
    test_types  = [t for t in LEAK_TYPE_ORDER   if t != "unknown"]

    # Build contingency table, dropping all-zero rows
    table_rows = []
    for group in test_groups:
        row = [matrix.get(group, {}).get(t, 0) for t in test_types]
        if sum(row) > 0:
            table_rows.append(row)

    if len(table_rows) < 2:
        return {
            "valid": False,
            "note": (
                "Insufficient data: need at least 2 non-empty cause groups "
                "for a chi-square test."
            ),
        }

    arr = np.array(table_rows, dtype=float)

    # Drop all-zero columns
    col_mask = arr.sum(axis=0) > 0
    arr = arr[:, col_mask]
    if arr.shape[1] < 2:
        return {
            "valid": False,
            "note": "Too few non-empty leak type columns for chi-square test.",
        }

    try:
        chi2, p, dof, expected = stats.chi2_contingency(arr)
        low_cells = int((expected < 5).sum())
        return {
            "valid": True,
            "chi2": round(float(chi2), 4),
            "p_value": round(float(p), 6),
            "degrees_of_freedom": int(dof),
            "cells_with_expected_below_5": low_cells,
            "note": (
                "Excludes 'Unknown / Not disclosed' cause group and 'unknown' leak type. "
                + (
                    f"{low_cells} cell(s) have expected count < 5 — "
                    "interpret chi-square result with caution."
                    if low_cells > 0
                    else "All expected cell counts ≥ 5."
                )
            ),
        }
    except ValueError as exc:
        return {"valid": False, "note": f"Chi-square could not be computed: {exc}"}


async def run(
    db: AsyncSession,
    diagnostic_status: str | None = None,
    gender: str | None = None,
    age_band: str | None = None,
    country: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> dict:
    conditions, params = member_filter_parts(country, gender, age_band, year_from, year_to)
    base_conditions = [
        f"ms.status_value IN ({SUFFERER_STATUSES_SQL})",
        "lt.leak_type != 'notRelevant'",
    ] + conditions

    if diagnostic_status:
        base_conditions.append("ms.status_value = :diagnostic_status")
        params["diagnostic_status"] = diagnostic_status

    base_where = where_clause(base_conditions)

    # ── Raw cell counts: individual cause × leak_type ─────────────────────────
    raw_rows = (await db.execute(text(f"""
        SELECT c.cause, lt.leak_type, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {base_where}
        GROUP BY c.cause, lt.leak_type
    """), params)).fetchall()

    # Individual cause totals (across all leak types)
    cause_totals_rows = (await db.execute(text(f"""
        SELECT c.cause, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {where_clause([f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + conditions + ([f"ms.status_value = :diagnostic_status"] if diagnostic_status else []))}
        GROUP BY c.cause
    """), params)).fetchall()
    cause_totals: dict[str, int] = {r.cause: r.cnt for r in cause_totals_rows}

    # ── Build (cause, leak_type) → count matrix ───────────────────────────────
    raw_matrix: dict[str, dict[str, int]] = defaultdict(dict)
    for r in raw_rows:
        raw_matrix[r.cause][r.leak_type] = r.cnt

    # ── Group-level aggregation ───────────────────────────────────────────────
    # group_matrix[group_name][leak_type] = COUNT(DISTINCT members with that group + type)
    group_matrix_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, lt.leak_type,
               COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN csf_leak_types lt ON m.pseudo_id = lt.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {base_where}
        GROUP BY cause_group, lt.leak_type
    """), params)).fetchall()

    group_matrix: dict[str, dict[str, int]] = defaultdict(dict)
    for r in group_matrix_rows:
        group_matrix[r.cause_group][r.leak_type] = r.cnt

    # Group totals (members with that group × any leak type shown)
    group_totals_rows = (await db.execute(text(f"""
        SELECT ({CAUSE_GROUP_CASE_EXPR}) AS cause_group, COUNT(DISTINCT m.pseudo_id) AS cnt
        FROM members m
        JOIN causes_of_leak c ON m.pseudo_id = c.pseudo_id
        JOIN member_statuses ms ON m.pseudo_id = ms.pseudo_id
        {where_clause([f"ms.status_value IN ({SUFFERER_STATUSES_SQL})"] + conditions + ([f"ms.status_value = :diagnostic_status"] if diagnostic_status else []))}
        GROUP BY cause_group
    """), params)).fetchall()
    group_totals: dict[str, int] = {r.cause_group: r.cnt for r in group_totals_rows}

    # ── Assemble matrix rows ──────────────────────────────────────────────────
    matrix_rows = []
    for group_name in CAUSE_GROUP_ORDER:
        # Group header row
        group_row: dict = {
            "type": "group",
            "label": group_name,
            "total": cell(group_totals.get(group_name, 0)),
        }
        group_row_total = 0
        for lt in LEAK_TYPE_ORDER:
            cnt = group_matrix.get(group_name, {}).get(lt, 0)
            group_row[lt] = cell(cnt)
            group_row_total += cnt
        group_row["row_total"] = cell(group_row_total)
        matrix_rows.append(group_row)

        # Individual cause rows within this group
        for cause in sorted(CAUSE_GROUPS.get(group_name, frozenset())):
            if cause not in cause_totals and cause not in raw_matrix:
                continue  # omit causes with zero members
            cause_row: dict = {
                "type": "individual",
                "label": cause,
                "cause_group": group_name,
                "total": cell(cause_totals.get(cause, 0)),
            }
            cause_row_total = 0
            for lt in LEAK_TYPE_ORDER:
                cnt = raw_matrix.get(cause, {}).get(lt, 0)
                cause_row[lt] = cell(cnt)
                cause_row_total += cnt
            cause_row["row_total"] = cell(cause_row_total)
            cause_row["pct_of_row"] = {
                lt: pct(raw_matrix.get(cause, {}).get(lt, 0), cause_row_total)
                for lt in LEAK_TYPE_ORDER
            }
            matrix_rows.append(cause_row)

    # ── Chi-square test ───────────────────────────────────────────────────────
    chi_sq = _chi_square(group_matrix)

    return {
        "filters_applied": {
            "diagnostic_status": diagnostic_status,
            "gender": gender,
            "age_band": age_band,
            "country": country,
            "year_from": year_from,
            "year_to": year_to,
        },
        "leak_type_columns": LEAK_TYPE_ORDER,
        "matrix": matrix_rows,
        "denominator_note": (
            "Each cell is COUNT(DISTINCT members) with that cause AND that leak type. "
            "A member with two causes appears in two rows; a member with two leak types "
            "appears in two columns. Row totals do not sum to total cohort size."
        ),
        "chi_square_test": chi_sq,
    }
