"""
Geographic filter — determines whether a member record is in scope.

Scope: UK (all country name variants) and EEA member states.
Logic: allowlist only — any country not on this list is excluded.
Fail-closed: empty and null country values are excluded, not assumed to be in scope.

Any changes to this allowlist require review against:
  - EU GDPR Article 3(2) territorial scope
  - ICO registration scope
  - Data Architecture Spec v0.2 Section 3
"""
from __future__ import annotations

# All accepted UK country name variants — case-insensitive match applied at runtime.
_UK_VARIANTS: frozenset[str] = frozenset({
    "england",
    "scotland",
    "wales",
    "northern ireland",
    "united kingdom",
    "uk",
    "great britain",
})

# EU 27 member states + 3 EEA non-EU members (Iceland, Liechtenstein, Norway).
# Total: 30 values.
_EEA_COUNTRIES: frozenset[str] = frozenset({
    # EU 27
    "austria",
    "belgium",
    "bulgaria",
    "croatia",
    "cyprus",
    "czech republic",
    "czechia",          # alternative spelling accepted
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "ireland",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "malta",
    "netherlands",
    "poland",
    "portugal",
    "romania",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    # EEA non-EU
    "iceland",
    "liechtenstein",
    "norway",
})

# Combined allowlist — used by is_in_scope()
IN_SCOPE_COUNTRIES: frozenset[str] = _UK_VARIANTS | _EEA_COUNTRIES


def is_in_scope(country: str | None) -> bool:
    """
    Return True if the country value is in the UK/EEA allowlist.

    Empty and null values return False — fail closed.
    Matching is case-insensitive after stripping whitespace.
    """
    if not country or not country.strip():
        return False
    return country.strip().lower() in IN_SCOPE_COUNTRIES


def skip_reason(country: str | None) -> str:
    """
    Return the log token used when a record is excluded by the geographic filter.

    Used in import batch notes and audit log entries.
    """
    if not country or not country.strip():
        return "out_of_scope_geography_empty"
    return "out_of_scope_geography"
