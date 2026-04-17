"""
Field transformation tests.

These tests verify the pure transformation functions that convert raw
membership export fields into research-safe equivalents.

See Data Architecture Spec v0.2 Section 4 and Test Strategy v0.1 Section 5.
"""

import pytest
from datetime import date

from pipeline.field_transform import (
    to_age_band,
    to_outward_code,
    to_membership_year,
    normalise_gender,
)


# ── Age band tests ────────────────────────────────────────────────────────────

class TestToAgeBand:
    """
    Age bands are computed relative to today's date, so tests use
    date-of-birth values that are known to be in each band for any
    plausible test run date.

    Vocabulary: under_18 | 18_25 | 26_34 | 35_49 | 50_69 | 70_79 | 80_89 | 90_plus
    """

    def _dob_for_age(self, age: int) -> str:
        """Return an ISO date-of-birth that gives exactly `age` years today."""
        today = date.today()
        dob = today.replace(year=today.year - age)
        return dob.isoformat()

    # ── Mid-band values ───────────────────────────────────────────────────────

    def test_under_18(self) -> None:
        dob = self._dob_for_age(15)
        assert to_age_band(dob) == "under_18"

    def test_18_25_mid(self) -> None:
        dob = self._dob_for_age(21)
        assert to_age_band(dob) == "18_25"

    def test_26_34_mid(self) -> None:
        dob = self._dob_for_age(30)
        assert to_age_band(dob) == "26_34"

    def test_35_49_mid(self) -> None:
        dob = self._dob_for_age(42)
        assert to_age_band(dob) == "35_49"

    def test_50_69_mid(self) -> None:
        dob = self._dob_for_age(60)
        assert to_age_band(dob) == "50_69"

    def test_70_79_mid(self) -> None:
        dob = self._dob_for_age(75)
        assert to_age_band(dob) == "70_79"

    def test_80_89_mid(self) -> None:
        dob = self._dob_for_age(85)
        assert to_age_band(dob) == "80_89"

    def test_90_plus(self) -> None:
        dob = self._dob_for_age(95)
        assert to_age_band(dob) == "90_plus"

    # ── Null / invalid input ──────────────────────────────────────────────────

    def test_none_returns_none(self) -> None:
        assert to_age_band(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert to_age_band("") is None

    def test_invalid_date_returns_none(self) -> None:
        assert to_age_band("not-a-date") is None

    def test_partial_date_returns_none(self) -> None:
        assert to_age_band("1982") is None

    def test_datetime_string_truncated_correctly(self) -> None:
        """Datetime strings with a time component must be handled via [:10] slicing."""
        dob = self._dob_for_age(40)
        dob_with_time = dob + "T00:00:00"
        assert to_age_band(dob_with_time) == "35_49"

    # ── Exact boundary cutpoints ──────────────────────────────────────────────

    @pytest.mark.parametrize("age,expected_band", [
        # under_18 / 18_25 boundary
        (17, "under_18"),
        (18, "18_25"),
        # 18_25 / 26_34 boundary
        (25, "18_25"),
        (26, "26_34"),
        # 26_34 / 35_49 boundary
        (34, "26_34"),
        (35, "35_49"),
        # 35_49 / 50_69 boundary
        (49, "35_49"),
        (50, "50_69"),
        # 50_69 / 70_79 boundary
        (69, "50_69"),
        (70, "70_79"),
        # 70_79 / 80_89 boundary
        (79, "70_79"),
        (80, "80_89"),
        # 80_89 / 90_plus boundary
        (89, "80_89"),
        (90, "90_plus"),
        # well above 90
        (100, "90_plus"),
    ])
    def test_age_band_boundaries(self, age: int, expected_band: str) -> None:
        dob = self._dob_for_age(age)
        assert to_age_band(dob) == expected_band


# ── Outward code tests ────────────────────────────────────────────────────────

class TestToOutwardCode:
    """UK postcode outward code extraction."""

    @pytest.mark.parametrize("postcode,expected", [
        ("SW1A 2AA", "SW1A"),
        ("M1 1AE", "M1"),
        ("B1 1AA", "B1"),
        ("EH1 1AA", "EH1"),
        ("G1 2GG", "G1"),
        ("CF10 1DD", "CF10"),
        ("BT1 1AA", "BT1"),
        ("LS1 1BA", "LS1"),
        ("BS1 4QA", "BS1"),
        ("L1 8JQ", "L1"),
        ("WC2N 5DU", "WC2N"),
        ("EC1A 1BB", "EC1A"),
        ("NW1 6XE", "NW1"),
        ("W1B 2EL", "W1B"),
        ("SE1 7PB", "SE1"),
        ("E1 6RF", "E1"),
        ("N1 9GU", "N1"),
        ("SW6 1AA", "SW6"),
    ])
    def test_uk_postcode_extraction(self, postcode: str, expected: str) -> None:
        assert to_outward_code(postcode) == expected

    @pytest.mark.parametrize("postcode", [
        "10117",       # German
        "20095",       # German
        "75001",       # French
        "69001",       # French
        "1000",        # Belgian
        "2000",        # Belgian
        "0150",        # Norwegian
        "28001",       # Spanish
        "1010",        # Austrian
    ])
    def test_all_digit_postcode_returns_none(self, postcode: str) -> None:
        assert to_outward_code(postcode) is None

    def test_none_returns_none(self) -> None:
        assert to_outward_code(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert to_outward_code("") is None

    def test_case_insensitive_input(self) -> None:
        assert to_outward_code("sw1a 2aa") == "SW1A"

    def test_no_space_format(self) -> None:
        """Postcodes formatted without space: SW1A2AA → SW1A"""
        assert to_outward_code("SW1A2AA") == "SW1A"


# ── Membership year tests ─────────────────────────────────────────────────────

class TestToMembershipYear:

    @pytest.mark.parametrize("date_str,expected_year", [
        ("2019-03-15", 2019),
        ("2018-07-20", 2018),
        ("2024-12-31", 2024),
        ("2017-01-01", 2017),
    ])
    def test_extracts_year(self, date_str: str, expected_year: int) -> None:
        assert to_membership_year(date_str) == expected_year

    def test_none_returns_none(self) -> None:
        assert to_membership_year(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert to_membership_year("") is None

    def test_invalid_date_returns_none(self) -> None:
        assert to_membership_year("not-a-date") is None

    def test_datetime_string_handled(self) -> None:
        assert to_membership_year("2021-06-15T10:30:00") == 2021


# ── Gender normalisation tests ────────────────────────────────────────────────

class TestNormaliseGender:

    @pytest.mark.parametrize("value,expected", [
        ("male", "male"),
        ("female", "female"),
        ("Male", "male"),
        ("Female", "female"),
        ("MALE", "male"),
        ("FEMALE", "female"),
        ("  male  ", "male"),
    ])
    def test_valid_gender_normalised(self, value: str, expected: str) -> None:
        assert normalise_gender(value) == expected

    @pytest.mark.parametrize("value", [
        "other",
        "non-binary",
        "prefer not to say",
        "unknown",
        "m",
        "f",
        "1",
    ])
    def test_invalid_gender_returns_none(self, value: str) -> None:
        assert normalise_gender(value) is None

    def test_none_returns_none(self) -> None:
        assert normalise_gender(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert normalise_gender("") is None
