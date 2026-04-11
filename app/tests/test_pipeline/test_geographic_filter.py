"""
Geographic filter tests — BLOCKING.

These tests verify the in-scope country allowlist that prevents non-UK/EEA
records from entering the research database.

All tests in this file are BLOCKING — the pipeline must not be deployed
without every test here passing. See Test Strategy v0.1 Section 4.2.
"""

import pytest

from pipeline.geographic_filter import is_in_scope, skip_reason, IN_SCOPE_COUNTRIES


# ── UK country variant tests ───────────────────────────────────────────────────

class TestUKVariants:
    """All seven UK country name variants must be accepted."""

    @pytest.mark.parametrize("country", [
        "England",
        "Scotland",
        "Wales",
        "Northern Ireland",
        "United Kingdom",
        "UK",
        "Great Britain",
    ])
    def test_uk_variant_accepted(self, country: str) -> None:
        assert is_in_scope(country), f"Expected {country!r} to be in scope"

    @pytest.mark.parametrize("country", [
        "england",
        "ENGLAND",
        "  England  ",
        "united kingdom",
        "UNITED KINGDOM",
        "uk",
    ])
    def test_uk_variant_case_insensitive(self, country: str) -> None:
        assert is_in_scope(country), f"Expected {country!r} to be in scope (case-insensitive)"


# ── EEA country tests ─────────────────────────────────────────────────────────

class TestEEACountries:
    """All 27 EU member states + 3 EEA non-EU states must be accepted."""

    EU_27 = [
        "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus",
        "Czech Republic", "Denmark", "Estonia", "Finland", "France",
        "Germany", "Greece", "Hungary", "Ireland", "Italy",
        "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands",
        "Poland", "Portugal", "Romania", "Slovakia", "Slovenia",
        "Spain", "Sweden",
    ]

    EEA_NON_EU = ["Iceland", "Liechtenstein", "Norway"]

    @pytest.mark.parametrize("country", EU_27)
    def test_eu27_member_state_accepted(self, country: str) -> None:
        assert is_in_scope(country), f"EU27 member {country!r} not accepted"

    @pytest.mark.parametrize("country", EEA_NON_EU)
    def test_eea_non_eu_accepted(self, country: str) -> None:
        assert is_in_scope(country), f"EEA non-EU member {country!r} not accepted"

    def test_czechia_alternative_spelling_accepted(self) -> None:
        """Czech Republic has a common alternative: 'Czechia'. Both must be accepted."""
        assert is_in_scope("Czechia")

    def test_total_in_scope_countries_count(self) -> None:
        """
        Sanity check on the size of the allowlist.
        7 UK variants + 27 EU + 3 EEA non-EU = 37 values.
        Czechia adds an 8th UK/EU variant, giving 38.
        """
        uk_variants = {"england", "scotland", "wales", "northern ireland",
                       "united kingdom", "uk", "great britain"}
        eea_variants = set(c.lower() for c in self.EU_27 + self.EEA_NON_EU + ["Czechia"])
        expected_minimum = len(uk_variants) + len(eea_variants)
        assert len(IN_SCOPE_COUNTRIES) >= expected_minimum


# ── Out-of-scope country tests ─────────────────────────────────────────────────

class TestOutOfScopeCountries:
    """Countries outside UK/EEA must be rejected."""

    @pytest.mark.parametrize("country", [
        "United States",
        "Canada",
        "Australia",
        "New Zealand",
        "Japan",
        "Brazil",
        "South Africa",
        "India",
        "China",
    ])
    def test_non_european_country_rejected(self, country: str) -> None:
        assert not is_in_scope(country), f"Expected {country!r} to be out of scope"

    def test_ambiguous_country_rejected(self) -> None:
        """'Europa' is not a valid country value — not in allowlist."""
        assert not is_in_scope("Europa")

    def test_partial_match_rejected(self) -> None:
        """'Northern' without 'Ireland' must not match."""
        assert not is_in_scope("Northern")

    def test_united_states_abbreviation_rejected(self) -> None:
        """'US' must not be accepted — only 'UK' is in the allowlist."""
        assert not is_in_scope("US")


# ── Empty / null country tests ─────────────────────────────────────────────────

class TestEmptyCountry:
    """Empty and null country values must be excluded (fail closed)."""

    def test_none_country_excluded(self) -> None:
        assert not is_in_scope(None)

    def test_empty_string_excluded(self) -> None:
        assert not is_in_scope("")

    def test_whitespace_only_excluded(self) -> None:
        assert not is_in_scope("   ")

    def test_none_skip_reason(self) -> None:
        assert skip_reason(None) == "out_of_scope_geography_empty"

    def test_empty_skip_reason(self) -> None:
        assert skip_reason("") == "out_of_scope_geography_empty"

    def test_out_of_scope_skip_reason(self) -> None:
        assert skip_reason("United States") == "out_of_scope_geography"


# ── Mixed CSV fixture test ─────────────────────────────────────────────────────

class TestMixedCSVCounts:
    """
    Validate that applying the geographic filter to sample_import_mixed.csv
    produces exactly 30 in-scope and 20 out-of-scope records.

    sample_import_mixed.csv contains:
      - 30 UK/EU records  (IDs 2001–2030)
      - 10 United States  (IDs 2031–2040)
      - 5  Canada         (IDs 2041–2045)
      - 5  Australia      (IDs 2046–2050)
    Total: 50 records.
    """

    def test_mixed_csv_filter_counts(self, fixtures_dir) -> None:
        import csv

        csv_path = fixtures_dir / "sample_import_mixed.csv"
        in_scope = 0
        out_of_scope = 0

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if is_in_scope(row["country"]):
                    in_scope += 1
                else:
                    out_of_scope += 1

        assert in_scope == 30, f"Expected 30 in-scope records, got {in_scope}"
        assert out_of_scope == 20, f"Expected 20 out-of-scope records, got {out_of_scope}"

    def test_mixed_csv_no_us_in_scope(self, fixtures_dir) -> None:
        import csv

        csv_path = fixtures_dir / "sample_import_mixed.csv"
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            in_scope_countries = [
                row["country"]
                for row in reader
                if is_in_scope(row["country"])
            ]

        assert "United States" not in in_scope_countries
        assert "Canada" not in in_scope_countries
        assert "Australia" not in in_scope_countries
