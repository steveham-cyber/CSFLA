"""
Integration tests for Report 5 — Geographic Distribution.

Fixture summary (from standard_cohort):
  England  12  (UK — >=10, shown in by_country)
  Scotland  9  (UK — <10, suppressed from by_country via HAVING)
  Germany   2  (EU — <10, aggregated into "Other Europe")
  France    1  (EU — <10, aggregated into "Other Europe")

Tests:
  1. Happy path — correct structure, no errors
  2. UK by_country: England shown, Scotland suppressed
  3. Europe by_country: Germany/France aggregated into "Other Europe"
  4. country_group filter (uk / europe)
  5. Empty cohort — graceful zero result
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r5_geography


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r5_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)

    assert "filters_applied" in result
    assert "uk" in result
    assert "europe" in result
    assert "crosstab_cause_by_country" in result
    assert "crosstab_status_by_country" in result

    uk = result["uk"]
    assert "by_country" in uk
    assert "by_region" in uk
    assert "outward_code_density" in uk
    assert isinstance(uk["by_country"], list)
    assert isinstance(uk["by_region"], list)

    europe = result["europe"]
    assert "by_country" in europe
    assert isinstance(europe["by_country"], list)


async def test_r5_filters_applied_default(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)
    fa = result["filters_applied"]
    assert fa["country_group"] is None
    assert fa["diagnostic_status"] is None
    assert fa["leak_type"] is None
    assert fa["cause_group"] is None


# ── UK suppression ────────────────────────────────────────────────────────────

async def test_r5_england_shown_in_uk(db_session: AsyncSession, standard_cohort: dict):
    """England (12 members) meets k>=10 — must appear in uk.by_country."""
    result = await r5_geography.run(db_session)
    uk_countries = {r["country"] for r in result["uk"]["by_country"]}
    assert "England" in uk_countries


async def test_r5_scotland_suppressed_from_uk(db_session: AsyncSession, standard_cohort: dict):
    """Scotland (9 members) is below k=10 — HAVING filters it from uk.by_country."""
    result = await r5_geography.run(db_session)
    uk_countries = {r["country"] for r in result["uk"]["by_country"]}
    assert "Scotland" not in uk_countries


async def test_r5_england_count_correct(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)
    england = next(r for r in result["uk"]["by_country"] if r["country"] == "England")
    assert england["count"] == 12


# ── Europe aggregation ────────────────────────────────────────────────────────

async def test_r5_germany_france_aggregated_to_other_europe(db_session: AsyncSession, standard_cohort: dict):
    """Germany (2) and France (1) are each below k=10 — both roll up to 'Other Europe'."""
    result = await r5_geography.run(db_session)
    eu_countries = {r["country"] for r in result["europe"]["by_country"]}
    assert "Germany" not in eu_countries
    assert "France" not in eu_countries
    assert "Other Europe" in eu_countries


async def test_r5_other_europe_count(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)
    other = next(r for r in result["europe"]["by_country"] if r["country"] == "Other Europe")
    assert other["count"] == 3  # 2 Germany + 1 France


# ── country_group filter ──────────────────────────────────────────────────────

async def test_r5_filter_uk_only(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session, country_group="uk")

    assert result["filters_applied"]["country_group"] == "uk"
    # Europe breakdown still present (not affected by filter on cross-tabs)
    # but UK section should still have England
    uk_countries = {r["country"] for r in result["uk"]["by_country"]}
    assert "England" in uk_countries


async def test_r5_filter_europe_only(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session, country_group="europe")

    assert result["filters_applied"]["country_group"] == "europe"
    # UK by_country scoped to non-UK countries → England not shown
    uk_countries = {r["country"] for r in result["uk"]["by_country"]}
    assert "England" not in uk_countries


async def test_r5_filter_diagnostic_status(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session, diagnostic_status="csfLeakSuffererDiagnosed")

    assert result["filters_applied"]["diagnostic_status"] == "csfLeakSuffererDiagnosed"
    assert isinstance(result["uk"]["by_country"], list)


async def test_r5_filter_cause_group(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session, cause_group="Iatrogenic")

    assert result["filters_applied"]["cause_group"] == "Iatrogenic"
    assert isinstance(result["uk"]["by_country"], list)


# ── Cross-tab structure ───────────────────────────────────────────────────────

async def test_r5_crosstab_cause_by_country_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)
    for row in result["crosstab_cause_by_country"]:
        assert "country" in row
        assert "total" in row
        # total is a cell() value
        assert "suppressed" in row["total"]


async def test_r5_crosstab_status_by_country_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r5_geography.run(db_session)
    for row in result["crosstab_status_by_country"]:
        assert "country" in row
        assert "total" in row


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r5_empty_cohort(db_session: AsyncSession):
    result = await r5_geography.run(db_session)

    assert result["uk"]["by_country"] == []
    assert result["europe"]["by_country"] == []
    assert result["crosstab_cause_by_country"] == []
    assert result["crosstab_status_by_country"] == []
