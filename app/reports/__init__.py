"""
Report engine — shared constants, cause groupings, and filter utilities.

All report queries enforce MIN_COHORT_SIZE (k>=10) in HAVING clauses.
The 'm' alias is assumed to refer to the members table throughout.
"""
from __future__ import annotations

# ── k>=10 threshold ───────────────────────────────────────────────────────────

MIN_COHORT_SIZE = 10


# ── Controlled vocabularies ───────────────────────────────────────────────────

SUFFERER_STATUSES: frozenset[str] = frozenset({
    "csfLeakSuffererDiagnosed",
    "csfLeakSuffererSuspected",
    "formerCsfLeakSufferer",
})

SUFFERER_STATUSES_SQL = (
    "'csfLeakSuffererDiagnosed','csfLeakSuffererSuspected','formerCsfLeakSufferer'"
)

LEAK_TYPES_FOR_ANALYSIS: frozenset[str] = frozenset({
    "spinal", "cranial", "spinalAndCranial", "unknown",
})

# ── Cause groupings ───────────────────────────────────────────────────────────

CAUSE_GROUPS: dict[str, frozenset[str]] = {
    "Iatrogenic": frozenset({
        "spinalSurgery", "cranialSurgery", "lumbarPuncture",
        "epiduralAnaesthesia", "spinalAnaesthesia", "otherIatrogenicCause",
    }),
    "Connective Tissue Disorder": frozenset({
        "ehlersDanlosSyndrome", "marfanSyndrome",
        "otherHeritableDisorderOfConnectiveTissue",
    }),
    "Spontaneous / Structural (Spinal)": frozenset({
        "boneSpur", "cystTarlovPerineuralMeningeal", "sihNoStructuralLesion",
    }),
    "IIH-Related / Cranial": frozenset({
        "idiopathicIntracranialHypertension",
    }),
    "Traumatic": frozenset({"trauma"}),
    "Other": frozenset({"other"}),
    "Unknown / Not disclosed": frozenset({"unknown", "preferNotToSay"}),
}

# Reverse lookup: individual cause value → group name
CAUSE_TO_GROUP: dict[str, str] = {
    cause: group
    for group, causes in CAUSE_GROUPS.items()
    for cause in causes
}

CAUSE_GROUP_ORDER: list[str] = [
    "Iatrogenic",
    "Connective Tissue Disorder",
    "Spontaneous / Structural (Spinal)",
    "IIH-Related / Cranial",
    "Traumatic",
    "Other",
    "Unknown / Not disclosed",
]

LEAK_TYPE_ORDER: list[str] = ["spinal", "cranial", "spinalAndCranial", "unknown"]


# ── Filter builder ────────────────────────────────────────────────────────────

def member_filter_parts(
    country: str | None = None,
    gender: str | None = None,
    age_band: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> tuple[list[str], dict]:
    """
    Build WHERE conditions for the members table (alias 'm').

    Returns (conditions_list, params_dict). The caller appends conditions
    to their query's WHERE clause and merges params into their execute call.

    Status/cause/leak_type filters are NOT handled here — each report that
    uses them adds those JOINs and conditions directly.
    """
    conditions: list[str] = []
    params: dict = {}

    if country is not None:
        conditions.append("m.country = :country")
        params["country"] = country
    if gender is not None:
        conditions.append("m.gender = :gender")
        params["gender"] = gender
    if age_band is not None:
        conditions.append("m.age_band = :age_band")
        params["age_band"] = age_band
    if year_from is not None:
        conditions.append("m.member_since_year >= :year_from")
        params["year_from"] = year_from
    if year_to is not None:
        conditions.append("m.member_since_year <= :year_to")
        params["year_to"] = year_to

    return conditions, params


def where_clause(conditions: list[str], prefix: str = "WHERE") -> str:
    """
    Join a list of conditions into a SQL WHERE (or AND) fragment.

    Returns empty string if no conditions. Caller chooses prefix
    ('WHERE' for the first block, 'AND' when appending to existing conditions).
    """
    if not conditions:
        return ""
    joined = " AND ".join(conditions)
    return f"{prefix} {joined}"


# ── Suppression helper ────────────────────────────────────────────────────────

def suppressed(count: int) -> dict:
    """Return a suppressed cell marker for groups below MIN_COHORT_SIZE."""
    return {"count": None, "suppressed": True}


def cell(count: int) -> dict:
    """Return a display-safe cell value, suppressing if below threshold."""
    if count < MIN_COHORT_SIZE:
        return suppressed(count)
    return {"count": count, "suppressed": False}


def pct(numerator: int, denominator: int) -> float | None:
    """Return rounded percentage, or None if denominator is zero."""
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


# ── Shared SQL fragment ───────────────────────────────────────────────────────

# CASE WHEN expression mapping cause values to cause group names.
# Assumes the causes_of_leak table is aliased as 'c' in the query.
# Uses controlled vocabulary only — safe to embed as string literals.
CAUSE_GROUP_CASE_EXPR: str = (
    "CASE "
    + " ".join(
        "WHEN c.cause IN ({}) THEN '{}'".format(
            ", ".join(f"'{v}'" for v in sorted(causes)), group
        )
        for group, causes in CAUSE_GROUPS.items()
    )
    + " ELSE 'Unknown / Not disclosed' END"
)
