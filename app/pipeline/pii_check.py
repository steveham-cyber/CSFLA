"""
PII field detection — secondary privacy gate.

The research DB must never contain any field on this strip list.
The pipeline uses an allowlist approach (only approved output fields are written),
but this check provides a belt-and-braces verification that the transformation
step produced a clean record.

If any PII field is found with a non-empty value the import is halted and
the database transaction is rolled back. No records from the batch are persisted.

See Data Architecture Spec v0.2 Section 4 (Strip List).
"""

# Fields that must never appear in a transformed record.
# Any key in this set that maps to a non-empty value is a pipeline failure.
PII_FIELDS: frozenset[str] = frozenset({
    "firstName",
    "lastName",
    "fullName",
    "email",
    "username",
    "password",
    "phoneNumber",
    "streetAddress",
    "townCity",
    "dateOfBirth",                          # full DOB stripped — only age_band retained
    "postcodeZipCode",                      # full postcode stripped — only outward code retained
    "cpEditUrl",
    "uid",
    "membershipNumber",
    "verificationCode",
    "lastLoginAttemptIp",
    "contactedAboutParticipationInResearch",
})

_EMPTY_VALUES = (None, "", [], {})


def check_for_pii(record: dict) -> list[str]:
    """
    Inspect a transformed record dict for any PII field that is present and non-empty.

    Args:
        record: The transformed record dict — must be the post-transformation output,
                not the raw import row.

    Returns:
        List of PII field names that are present and non-empty. Empty list = clean.
    """
    return [
        field
        for field in PII_FIELDS
        if field in record and record[field] not in _EMPTY_VALUES
    ]


def has_pii(record: dict) -> bool:
    """Return True if the record contains any PII field with a non-empty value."""
    return bool(check_for_pii(record))
