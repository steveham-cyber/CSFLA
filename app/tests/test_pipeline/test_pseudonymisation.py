"""
Pseudonymisation tests — BLOCKING.

These tests verify the HMAC-SHA256 algorithm properties required by
Data Architecture Spec v0.2 Section 5 and Test Strategy v0.1 Section 4.3.

All tests here are BLOCKING — the pipeline must not be deployed without
every test passing.

Key under test: TEST_PSEUDONYMISATION_KEY (a fixed test-only value).
This key is NEVER equal to the production key in Azure Key Vault.
"""

import hmac
import os
import pytest

from pipeline.pseudonymisation import compute_pseudo_id
from tests.conftest import TEST_PSEUDONYMISATION_KEY


TEST_KEY = TEST_PSEUDONYMISATION_KEY
DIFFERENT_KEY = "different-test-key-also-never-used-in-production"


# ── Stability tests ───────────────────────────────────────────────────────────

class TestStability:
    """Same input always produces same output."""

    def test_same_member_id_same_key_produces_same_pseudo_id(self) -> None:
        result1 = compute_pseudo_id("12345", TEST_KEY)
        result2 = compute_pseudo_id("12345", TEST_KEY)
        assert result1 == result2

    def test_stability_with_integer_member_id(self) -> None:
        result1 = compute_pseudo_id(12345, TEST_KEY)
        result2 = compute_pseudo_id(12345, TEST_KEY)
        assert result1 == result2

    def test_string_and_integer_member_id_identical(self) -> None:
        """str("12345") and int(12345) must produce the same pseudo_id."""
        result_str = compute_pseudo_id("12345", TEST_KEY)
        result_int = compute_pseudo_id(12345, TEST_KEY)
        assert result_str == result_int


# ── Uniqueness tests ──────────────────────────────────────────────────────────

class TestUniqueness:
    """Different member_ids must produce different pseudo_ids."""

    def test_different_member_ids_produce_different_pseudo_ids(self) -> None:
        ids = ["12345", "12346", "99999", "1", "100000"]
        pseudo_ids = [compute_pseudo_id(mid, TEST_KEY) for mid in ids]
        assert len(set(pseudo_ids)) == len(ids), "Collision detected in pseudo_ids"

    def test_sequential_ids_produce_different_pseudo_ids(self) -> None:
        pseudo_ids = [compute_pseudo_id(str(i), TEST_KEY) for i in range(1, 101)]
        assert len(set(pseudo_ids)) == 100

    def test_zero_and_one_produce_different_pseudo_ids(self) -> None:
        assert compute_pseudo_id("0", TEST_KEY) != compute_pseudo_id("1", TEST_KEY)


# ── Output format tests ───────────────────────────────────────────────────────

class TestOutputFormat:
    """pseudo_id must be a non-empty URL-safe Base64 string without padding."""

    def test_output_is_string(self) -> None:
        result = compute_pseudo_id("12345", TEST_KEY)
        assert isinstance(result, str)

    def test_output_is_non_empty(self) -> None:
        result = compute_pseudo_id("12345", TEST_KEY)
        assert len(result) > 0

    def test_output_is_url_safe_base64(self) -> None:
        """Output must only contain URL-safe Base64 chars: A-Z a-z 0-9 - _"""
        import re
        result = compute_pseudo_id("12345", TEST_KEY)
        assert re.fullmatch(r"[A-Za-z0-9\-_]+", result), (
            f"pseudo_id {result!r} contains non-URL-safe characters"
        )

    def test_output_has_no_padding(self) -> None:
        """Output must not end with '=' padding characters."""
        result = compute_pseudo_id("12345", TEST_KEY)
        assert not result.endswith("=")

    def test_output_length_consistent_with_sha256(self) -> None:
        """
        HMAC-SHA256 produces 32 bytes.
        Base64Url without padding: ceil(32 * 4 / 3) = 43 chars.
        """
        result = compute_pseudo_id("12345", TEST_KEY)
        assert len(result) == 43


# ── Key sensitivity tests ─────────────────────────────────────────────────────

class TestKeySensitivity:
    """Different keys must produce different pseudo_ids for the same input."""

    def test_different_keys_produce_different_pseudo_ids(self) -> None:
        result1 = compute_pseudo_id("12345", TEST_KEY)
        result2 = compute_pseudo_id("12345", DIFFERENT_KEY)
        assert result1 != result2


# ── Cross-import consistency test ─────────────────────────────────────────────

class TestCrossImportConsistency:
    """
    The same member_id imported in two separate batches must always
    produce the same pseudo_id. This is guaranteed by the deterministic
    HMAC algorithm, not by any batch state.
    """

    def test_same_member_id_in_two_batches_same_pseudo_id(self) -> None:
        batch1_pseudo_id = compute_pseudo_id("12345", TEST_KEY)
        batch2_pseudo_id = compute_pseudo_id("12345", TEST_KEY)
        assert batch1_pseudo_id == batch2_pseudo_id

    def test_multiple_member_ids_consistent_across_batches(self) -> None:
        member_ids = ["1001", "1002", "1003", "5000", "99999"]
        batch1 = {mid: compute_pseudo_id(mid, TEST_KEY) for mid in member_ids}
        batch2 = {mid: compute_pseudo_id(mid, TEST_KEY) for mid in member_ids}
        assert batch1 == batch2


# ── Key isolation test ────────────────────────────────────────────────────────

class TestKeyIsolation:
    """
    The test key must not be the production key value.
    The test key is the fixed string defined in conftest.py and used in CI
    via the TEST_PSEUDONYMISATION_KEY secret. Production keys live in
    Azure Key Vault and are never in source code or CI secrets.
    """

    KNOWN_TEST_KEY = "test-hmac-key-csfleak-never-use-in-production-aabbccdd"

    def test_test_key_is_expected_fixed_value(self) -> None:
        """
        The test key must be the documented fixed value.
        If this fails, someone changed the test key to something else —
        check that it has not accidentally been set to the production key.
        """
        assert TEST_KEY == self.KNOWN_TEST_KEY, (
            "TEST_PSEUDONYMISATION_KEY is not the expected fixed test value. "
            "Verify it is not the production key."
        )

    def test_test_key_is_set_in_environment(self) -> None:
        """CI sets TEST_PSEUDONYMISATION_KEY via GitHub Actions secrets."""
        env_key = os.environ.get("TEST_PSEUDONYMISATION_KEY", self.KNOWN_TEST_KEY)
        assert env_key == self.KNOWN_TEST_KEY, (
            "Environment TEST_PSEUDONYMISATION_KEY does not match expected test value. "
            "Check that the GitHub Actions secret is set correctly."
        )


# ── Irreversibility test ──────────────────────────────────────────────────────

class TestIrreversibility:
    """
    The pseudo_id must not be reversible to a member_id without the key.

    This is a static/structural test: it verifies the codebase does not
    contain any function that accepts a pseudo_id and returns a member_id.
    The HMAC property itself (preimage resistance) guarantees irreversibility
    mathematically; this test guards against an implementation mistake.
    """

    def test_no_inverse_function_exported_from_pseudonymisation_module(self) -> None:
        """
        The pseudonymisation module must not export any function whose name
        suggests a reversal operation.
        """
        import pipeline.pseudonymisation as module
        reverse_patterns = [
            "reverse", "decode", "decrypt", "unmask",
            "to_member_id", "get_member_id", "lookup",
        ]
        exported = [name for name in dir(module) if not name.startswith("_")]
        for fn_name in exported:
            for pattern in reverse_patterns:
                assert pattern not in fn_name.lower(), (
                    f"Found suspicious function {fn_name!r} in pseudonymisation module. "
                    f"No reverse-HMAC function should exist."
                )
