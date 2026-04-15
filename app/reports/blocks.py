"""
Block registry — the 8 available report blocks for the custom report builder.

Each entry in BLOCKS declares:
  - title / description  — displayed in the palette and canvas
  - filters              — list of filter kwarg names the block's run() accepts
  - run                  — reference to the report module's async run() function

run_block() dispatches to the correct run() function, passing only the filters
the block accepts and coercing year_from/year_to to int.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

import reports.r1_cohort    as r1
import reports.r2_status    as r2
import reports.r3_leak_type as r3
import reports.r4_cause     as r4
import reports.r5_geography as r5
import reports.r6_trends    as r6
import reports.r7_cause_type as r7
import reports.r8_referral  as r8


BLOCKS: dict[str, dict] = {
    "r1": {
        "title": "Cohort Overview",
        "description": "Whole-cohort snapshot: size, status composition, geographic spread, data completeness.",
        "filters": [],
        "run": r1.run,
    },
    "r2": {
        "title": "Diagnostic Status Profile",
        "description": "Sufferer status breakdown cross-tabulated with demographics.",
        "filters": ["country", "gender", "age_band", "year_from", "year_to"],
        "run": r2.run,
    },
    "r3": {
        "title": "CSF Leak Type Distribution",
        "description": "Leak type distribution for sufferers, cross-tabulated with demographics.",
        "filters": ["diagnostic_status", "country", "gender", "age_band", "year_from", "year_to"],
        "run": r3.run,
    },
    "r4": {
        "title": "Cause of Leak Analysis",
        "description": "Cause distribution by clinical grouping, with cross-tabulations.",
        "filters": [
            "cause_group", "individual_cause", "leak_type",
            "diagnostic_status", "country", "gender", "age_band", "year_from", "year_to",
        ],
        "run": r4.run,
    },
    "r5": {
        "title": "Geographic Distribution",
        "description": "UK and European geographic breakdown with density data.",
        "filters": ["country_group", "diagnostic_status", "leak_type", "cause_group"],
        "run": r5.run,
    },
    "r6": {
        "title": "Membership Growth & Trends",
        "description": "Time-series metrics across member_since_year.",
        "filters": ["diagnostic_status", "country", "leak_type", "cause_group"],
        "run": r6.run,
    },
    "r7": {
        "title": "Cause × Type Cross-Analysis",
        "description": "Research matrix: cause of leak × leak type, with chi-square test.",
        "filters": ["diagnostic_status", "gender", "age_band", "country", "year_from", "year_to"],
        "run": r7.run,
    },
    "r8": {
        "title": "Referral Source Analysis",
        "description": "How members heard about the charity.",
        "filters": ["year_from", "year_to", "country"],
        "run": r8.run,
    },
}

# All valid filter keys across all blocks — used for input validation
VALID_FILTER_KEYS: frozenset[str] = frozenset(
    key for block in BLOCKS.values() for key in block["filters"]
)

_INT_FILTER_KEYS: frozenset[str] = frozenset({"year_from", "year_to"})


async def run_block(
    db: AsyncSession,
    block_id: str,
    filters: dict[str, Any],
) -> dict:
    """
    Execute a single block with the given filters.

    Only filter keys declared in the block's 'filters' list are passed to run().
    Keys not in the block's filter list are silently ignored.
    year_from and year_to are coerced to int (they may arrive as strings from JSON).

    Raises ValueError for unknown block_id.
    """
    if block_id not in BLOCKS:
        raise ValueError(f"Unknown block: {block_id!r}")

    block = BLOCKS[block_id]
    accepted = block["filters"]

    kwargs: dict[str, Any] = {}
    for key in accepted:
        val = filters.get(key)
        if val is None:
            continue
        if key in _INT_FILTER_KEYS:
            try:
                val = int(val)
            except (TypeError, ValueError):
                continue
        kwargs[key] = val

    return await block["run"](db, **kwargs)
