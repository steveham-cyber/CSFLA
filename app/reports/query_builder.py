"""
Custom report query builder.

Builds and executes dynamic GROUP BY queries from a report definition.
Enforces k>=10 cohort suppression unconditionally on every query.

Field sources:
  members table         → country, gender, age_band          (alias m)
  csf_leak_types table  → leak_type                          (alias clt)
  causes_of_leak table  → cause_group, individual_cause      (alias col)
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from reports import (
    MIN_COHORT_SIZE,
    CAUSE_GROUPS,
    CAUSE_GROUP_ORDER,
    CAUSE_TO_GROUP,
)

# CASE WHEN expression mapping col.cause values to group names.
# Uses alias 'col' for causes_of_leak (the shared CAUSE_GROUP_CASE_EXPR
# in reports/__init__.py uses alias 'c' — this one uses 'col').
_CAUSE_GROUP_COL_EXPR: str = (
    "CASE "
    + " ".join(
        "WHEN col.cause IN ({}) THEN '{}'".format(
            ", ".join(f"'{v}'" for v in sorted(causes)),
            group,
        )
        for group, causes in CAUSE_GROUPS.items()
    )
    + " ELSE 'Unknown / Not disclosed' END"
)

# ── Field catalogue ───────────────────────────────────────────────────────

FIELD_ORDER: list[str] = [
    "country",
    "gender",
    "age_band",
    "leak_type",
    "cause_group",
    "individual_cause",
]

AVAILABLE_FIELDS: dict[str, dict] = {
    "country": {
        "label": "Country",
        "source": "members",
        "col_expr": "m.country",
        "dynamic": True,
    },
    "gender": {
        "label": "Gender",
        "source": "members",
        "col_expr": "m.gender",
        "dynamic": True,
    },
    "age_band": {
        "label": "Age Band",
        "source": "members",
        "col_expr": "m.age_band",
        "dynamic": True,
    },
    "leak_type": {
        "label": "CSF Leak Type",
        "source": "csf_leak_types",
        "col_expr": "clt.leak_type",
        "dynamic": False,
        "values": ["spinal", "cranial", "spinalAndCranial", "unknown"],
    },
    "cause_group": {
        "label": "Cause Group",
        "source": "causes_of_leak",
        "col_expr": _CAUSE_GROUP_COL_EXPR,
        "dynamic": False,
        "values": list(CAUSE_GROUP_ORDER),
    },
    "individual_cause": {
        "label": "Individual Cause",
        "source": "causes_of_leak",
        "col_expr": "col.cause",
        "dynamic": False,
        "values": sorted(CAUSE_TO_GROUP.keys()),
    },
}

VALID_FIELD_KEYS: frozenset[str] = frozenset(AVAILABLE_FIELDS.keys())


# ── Public API ────────────────────────────────────────────────────────────

async def get_fields(db: AsyncSession) -> list[dict]:
    """
    Return all available fields with labels and allowed values.
    Dynamic fields (country, gender, age_band) query DISTINCT from DB.
    Enum fields return hardcoded controlled vocabularies.
    """
    result = []
    for key in FIELD_ORDER:
        field = AVAILABLE_FIELDS[key]
        if field["dynamic"]:
            col = field["col_expr"]
            rows = (
                await db.execute(
                    text(
                        f"SELECT DISTINCT {col} FROM members m"
                        f" WHERE {col} IS NOT NULL ORDER BY {col}"
                    )
                )
            ).scalars().all()
            values = list(rows)
        else:
            values = field["values"]
        result.append({"key": key, "label": field["label"], "values": values})
    return result


async def run_query(
    db: AsyncSession,
    dimensions: list[str],
    filters: dict[str, list[str]],
) -> dict:
    """
    Execute a GROUP BY query for the given dimensions and filters.

    Returns:
        {
            "columns": [...],
            "rows": [{"dim1": v, ..., "member_count": n}, ...],
            "total_shown": int,
            "suppressed_count": int,
        }

    k<10 combinations are excluded from rows and counted in suppressed_count.
    COUNT(DISTINCT m.pseudo_id) is used throughout to avoid double-counting
    when joining one-to-many tables.
    """
    all_fields = set(dimensions) | set(filters.keys())

    needs_leak = any(
        AVAILABLE_FIELDS[f]["source"] == "csf_leak_types" for f in all_fields
    )
    needs_cause = any(
        AVAILABLE_FIELDS[f]["source"] == "causes_of_leak" for f in all_fields
    )

    # ── SELECT and GROUP BY expressions ──────────────────────────────────
    select_exprs: list[str] = []
    group_exprs: list[str] = []

    for dim in dimensions:
        col = AVAILABLE_FIELDS[dim]["col_expr"]
        select_exprs.append(f"{col} AS {dim}")
        group_exprs.append(col)

    select_exprs.append("COUNT(DISTINCT m.pseudo_id) AS member_count")

    # ── FROM + JOINs ──────────────────────────────────────────────────────
    from_parts = ["FROM members m"]
    if needs_leak:
        from_parts.append(
            "LEFT JOIN csf_leak_types clt ON clt.pseudo_id = m.pseudo_id"
        )
    if needs_cause:
        from_parts.append(
            "LEFT JOIN causes_of_leak col ON col.pseudo_id = m.pseudo_id"
        )
    from_sql = "\n        ".join(from_parts)

    # ── WHERE conditions ──────────────────────────────────────────────────
    conditions: list[str] = []
    params: dict = {"min_cohort": MIN_COHORT_SIZE}

    for field_key, values in filters.items():
        if not values:
            continue

        if field_key == "cause_group":
            # Translate group names → individual cause values for WHERE clause.
            # (The CASE WHEN expression is only in SELECT/GROUP BY.)
            individual_causes = [
                cause
                for cause, grp in CAUSE_TO_GROUP.items()
                if grp in values
            ]
            if individual_causes:
                pnames = [f"fg_{i}" for i in range(len(individual_causes))]
                placeholders = ", ".join(f":{p}" for p in pnames)
                conditions.append(f"col.cause IN ({placeholders})")
                for pname, val in zip(pnames, individual_causes):
                    params[pname] = val
        else:
            col_expr = AVAILABLE_FIELDS[field_key]["col_expr"]
            pnames = [f"f_{field_key}_{i}" for i in range(len(values))]
            placeholders = ", ".join(f":{p}" for p in pnames)
            conditions.append(f"{col_expr} IN ({placeholders})")
            for pname, val in zip(pnames, values):
                params[pname] = val

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    group_sql = ("GROUP BY " + ", ".join(group_exprs)) if group_exprs else ""
    order_sql = ("ORDER BY " + ", ".join(group_exprs)) if group_exprs else ""

    # ── Main query ────────────────────────────────────────────────────────
    main_q = f"""
        SELECT {", ".join(select_exprs)}
        {from_sql}
        {where_sql}
        {group_sql}
        HAVING COUNT(DISTINCT m.pseudo_id) >= :min_cohort
        {order_sql}
    """

    # ── Suppressed count query ────────────────────────────────────────────
    suppressed_q = f"""
        SELECT COUNT(*) FROM (
            SELECT COUNT(DISTINCT m.pseudo_id) AS n
            {from_sql}
            {where_sql}
            {group_sql}
            HAVING COUNT(DISTINCT m.pseudo_id) < :min_cohort
        ) suppressed
    """

    rows = (await db.execute(text(main_q), params)).fetchall()
    suppressed_count: int = (
        await db.execute(text(suppressed_q), params)
    ).scalar() or 0

    result_rows = []
    for row in rows:
        row_dict = {dim: row[i] for i, dim in enumerate(dimensions)}
        row_dict["member_count"] = row[len(dimensions)]
        result_rows.append(row_dict)

    return {
        "columns": dimensions,
        "rows": result_rows,
        "total_shown": sum(r["member_count"] for r in result_rows),
        "suppressed_count": suppressed_count,
    }
