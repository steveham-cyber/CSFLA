"""
Field transformation functions.

Pure functions — no I/O, no database access, no Key Vault calls.
Each function takes a raw field value from the import CSV and returns
the research-safe equivalent as defined in Data Architecture Spec v0.2 Section 4.
"""

from __future__ import annotations
from datetime import date


# ── Age band ──────────────────────────────────────────────────────────────────

# Ordered list of (upper-bound-exclusive, band-label) pairs.
# Evaluated top-to-bottom; first match wins.
_AGE_BAND_THRESHOLDS: list[tuple[int, str]] = [
    (18, "under_18"),
    (30, "18_29"),
    (40, "30_39"),
    (50, "40_49"),
    (60, "50_59"),
    (70, "60_69"),
]
_BAND_70_OVER = "70_over"


def to_age_band(date_of_birth: str | None) -> str | None:
    """
    Convert an ISO date-of-birth string (YYYY-MM-DD) to a decade age band.

    Bands: under_18 | 18_29 | 30_39 | 40_49 | 50_59 | 60_69 | 70_over

    Returns None if the value is missing, empty, or not a parseable date.
    Age is calculated relative to today's date.
    """
    if not date_of_birth:
        return None
    try:
        dob = date.fromisoformat(str(date_of_birth)[:10])
    except (ValueError, TypeError):
        return None

    today = date.today()
    age = today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )

    for threshold, band in _AGE_BAND_THRESHOLDS:
        if age < threshold:
            return band
    return _BAND_70_OVER


# ── Outward code ──────────────────────────────────────────────────────────────

def to_outward_code(postcode: str | None) -> str | None:
    """
    Extract the outward (district) code from a UK postcode.

    UK format: <outward> <inward>, where inward is always 3 chars (digit + 2 letters).
    Examples: SW1A 2AA → SW1A | M1 1AE → M1 | BT1 1AA → BT1 | EH1 1AA → EH1

    Non-UK format postcodes (e.g. German all-digit codes) return None — the full
    postcode is not retained for non-UK records.

    Returns None if the postcode is empty, too short, or all-numeric.
    """
    if not postcode:
        return None

    clean = postcode.strip()

    # All-digit postcode (e.g. German "10117") — not a UK format, strip entirely.
    if clean.replace(" ", "").isdigit():
        return None

    clean = clean.upper()

    if " " in clean:
        outward = clean.split(" ")[0]
        return outward if len(outward) >= 2 else None

    # No space in string — UK inward code is always 3 chars.
    # Examples: SW1A2AA → SW1A, M11AE → M1
    if len(clean) >= 5:
        outward = clean[:-3]
        return outward if len(outward) >= 2 else None

    return None


# ── Membership year ───────────────────────────────────────────────────────────

def to_membership_year(date_string: str | None) -> int | None:
    """
    Extract the year component from a memberSince ISO date string.

    Only the year is retained — no month or day.
    Returns None if the value is missing or unparseable.
    """
    if not date_string:
        return None
    try:
        return date.fromisoformat(str(date_string)[:10]).year
    except (ValueError, TypeError):
        return None


# ── Gender normalisation ──────────────────────────────────────────────────────

_VALID_GENDERS: frozenset[str] = frozenset({"male", "female"})


def normalise_gender(gender: str | None) -> str | None:
    """
    Normalise gender to controlled vocabulary: 'male' | 'female' | None.

    Any value not in {male, female} is suppressed to None.
    Matching is case-insensitive after stripping whitespace.
    """
    if not gender:
        return None
    normalised = gender.strip().lower()
    return normalised if normalised in _VALID_GENDERS else None
