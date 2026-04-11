"""
PII detection tests — BLOCKING.

These tests verify that the PII check correctly identifies any residual
PII fields in a transformed record, and that a patched pipeline halts
the import when PII is found.

All tests here are BLOCKING. See Test Strategy v0.1 Section 4.1.

Note: The full pipeline is locked (ACTIONS.md A-07, A-10). The
test_pipeline_halts_on_pii_detection test uses a stub/mock to
simulate a pipeline that skips a strip step. Once the pipeline is
unlocked, these stubs will be replaced with the real pipeline call.
"""

import pytest

from pipeline.pii_check import check_for_pii, has_pii, PII_FIELDS


# ── Clean record tests ────────────────────────────────────────────────────────

class TestCleanRecord:
    """A fully transformed record must pass the PII check."""

    def _clean_record(self) -> dict:
        """A valid post-transformation record with no PII fields."""
        return {
            "pseudo_id": "abc123XYZ_urlsafe",
            "age_band": "30_39",
            "gender": "female",
            "country": "England",
            "region": None,
            "outward_code": "SW1A",
            "member_since_year": 2019,
            "referral_source": ["socialMedia"],
        }

    def test_clean_record_has_no_pii(self) -> None:
        record = self._clean_record()
        assert check_for_pii(record) == []

    def test_clean_record_has_pii_returns_false(self) -> None:
        record = self._clean_record()
        assert has_pii(record) is False

    def test_empty_record_has_no_pii(self) -> None:
        assert check_for_pii({}) == []


# ── PII field detection tests ─────────────────────────────────────────────────

class TestPIIFieldDetection:
    """Each PII field in the strip list must be detected if present."""

    @pytest.mark.parametrize("pii_field,value", [
        ("firstName", "Alice"),
        ("lastName", "Anderson"),
        ("fullName", "Alice Anderson"),
        ("email", "alice@example.com"),
        ("username", "aalice_001"),
        ("password", "$2b$12$somehash"),
        ("phoneNumber", "07700 001001"),
        ("streetAddress", "1 Test Street"),
        ("townCity", "London"),
        ("dateOfBirth", "1982-05-10"),
        ("postcodeZipCode", "SW1A 1AA"),
        ("cpEditUrl", "https://app.example.org/edit/1001"),
        ("uid", "uid_1001"),
        ("membershipNumber", "CSFL-1001"),
        ("verificationCode", "VER-1001-XXXX"),
        ("lastLoginAttemptIp", "192.168.1.1"),
        ("contactedAboutParticipationInResearch", "false"),
    ])
    def test_pii_field_detected(self, pii_field: str, value: str) -> None:
        record = {pii_field: value}
        detected = check_for_pii(record)
        assert pii_field in detected, (
            f"PII field {pii_field!r} not detected by check_for_pii"
        )

    def test_all_pii_fields_detected_simultaneously(self) -> None:
        """A record containing every PII field must report all of them."""
        record = {field: "test_value" for field in PII_FIELDS}
        detected = check_for_pii(record)
        assert set(detected) == set(PII_FIELDS)

    def test_multiple_pii_fields_all_returned(self) -> None:
        record = {
            "firstName": "Alice",
            "email": "alice@example.com",
            "pseudo_id": "abc123",     # allowed field — should not be flagged
        }
        detected = check_for_pii(record)
        assert "firstName" in detected
        assert "email" in detected
        assert "pseudo_id" not in detected


# ── Empty / null PII value tests ──────────────────────────────────────────────

class TestEmptyPIIValues:
    """PII fields with empty or null values must NOT trigger the check."""

    @pytest.mark.parametrize("empty_value", [None, "", [], {}])
    def test_null_pii_field_not_detected(self, empty_value) -> None:
        record = {"firstName": empty_value}
        assert check_for_pii(record) == []

    def test_empty_string_email_not_detected(self) -> None:
        record = {"email": ""}
        assert check_for_pii(record) == []


# ── Strip list completeness tests ─────────────────────────────────────────────

class TestStripListCompleteness:
    """The strip list must cover every field identified in the privacy analysis."""

    REQUIRED_PII_FIELDS = {
        "firstName", "lastName", "fullName",
        "email", "username", "password",
        "phoneNumber", "streetAddress", "townCity",
        "dateOfBirth", "postcodeZipCode",
        "cpEditUrl", "uid", "membershipNumber",
        "verificationCode", "lastLoginAttemptIp",
        "contactedAboutParticipationInResearch",
    }

    def test_all_required_fields_in_strip_list(self) -> None:
        missing = self.REQUIRED_PII_FIELDS - PII_FIELDS
        assert not missing, (
            f"These PII fields are missing from the strip list: {missing}"
        )


# ── Pipeline halt simulation test ─────────────────────────────────────────────

class TestPipelineHaltOnPII:
    """
    Simulate a pipeline that skips a strip step and verify the PII check
    catches it.

    The full pipeline is locked (see pipeline/__init__.py). This test
    uses a minimal stub that mimics the check that will live inside
    the full pipeline: if check_for_pii returns any fields, raise and
    rollback.
    """

    def _simulate_transform_with_missing_strip(self, raw_record: dict) -> dict:
        """
        Simulate a transformation that forgot to strip PII fields.
        Returns the raw record unmodified — as if the strip step was skipped.
        """
        return dict(raw_record)

    def _simulate_pii_check_gate(self, transformed_record: dict) -> None:
        """
        Simulate the PII check gate in the pipeline.
        Raises RuntimeError if any PII field is present — triggering rollback.
        """
        offending = check_for_pii(transformed_record)
        if offending:
            raise RuntimeError(
                f"PII check failed — fields present in transformed record: {offending}. "
                "Import halted. Database transaction must be rolled back."
            )

    def test_pii_check_raises_when_strip_skipped(self) -> None:
        raw = {
            "id": "1001",
            "firstName": "Alice",
            "email": "alice@example.com",
            "country": "England",
            "memberStatus": "csfLeakSuffererDiagnosed",
        }
        # Pipeline 'forgets' to strip — returns raw record
        transformed = self._simulate_transform_with_missing_strip(raw)

        with pytest.raises(RuntimeError, match="PII check failed"):
            self._simulate_pii_check_gate(transformed)

    def test_pii_check_does_not_raise_on_clean_record(self) -> None:
        clean = {
            "pseudo_id": "abc123XYZ",
            "age_band": "30_39",
            "gender": "female",
            "country": "England",
            "outward_code": "SW1A",
        }
        # Should not raise
        self._simulate_pii_check_gate(clean)

    def test_pii_check_error_message_names_offending_fields(self) -> None:
        record_with_pii = {"firstName": "Alice", "email": "alice@example.com"}
        with pytest.raises(RuntimeError) as exc_info:
            self._simulate_pii_check_gate(record_with_pii)
        error_message = str(exc_info.value)
        assert "firstName" in error_message or "email" in error_message
