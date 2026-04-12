"""
Integration tests for Report 6 — Membership Growth and Cohort Trends.

Fixture summary (from standard_cohort):
  England  12  sufferers  member_since_year=2020
  Scotland  9  sufferers  member_since_year=2021
  Germany   2  sufferers  member_since_year=2022
  France    1  sufferer   member_since_year=2023

Year range: 2020-2023 → 4 distinct years >= 3 → trend_charts_available=True

Per-year sufferer counts:
  2020: 12  (>=10 → cause/type breakdown NOT suppressed)
  2021:  9  (<10  → breakdown suppressed)
  2022:  2  (<10  → breakdown suppressed)
  2023:  1  (<10  → breakdown suppressed)

Tests:
  1. Happy path — correct structure, trend_charts_available=True
  2. Year range correct (2020-2023)
  3. Per-year suppression logic
  4. scope_note present
  5. Filter smoke tests
  6. Empty cohort — graceful zero result
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r6_trends


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r6_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session)

    assert "filters_applied" in result
    assert "year_range" in result
    assert "trend_charts_available" in result
    assert "scope_note" in result
    assert "by_year" in result

    yr = result["year_range"]
    assert "first_year" in yr
    assert "last_year" in yr
    assert "distinct_years" in yr

    assert isinstance(result["by_year"], list)


async def test_r6_trend_charts_available(db_session: AsyncSession, standard_cohort: dict):
    """4 distinct years (2020-2023) >= 3 → trend_charts_available=True."""
    result = await r6_trends.run(db_session)
    assert result["trend_charts_available"] is True


async def test_r6_year_range(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session)
    yr = result["year_range"]
    assert yr["first_year"] == 2020
    assert yr["last_year"] == 2023
    assert yr["distinct_years"] == 4


async def test_r6_all_years_present(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session)
    years = {row["year"] for row in result["by_year"]}
    assert years == {2020, 2021, 2022, 2023}


async def test_r6_scope_note_references_member_since_year(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session)
    assert "member_since_year" in result["scope_note"]


# ── Per-year structure ────────────────────────────────────────────────────────

async def test_r6_per_year_row_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session)
    for row in result["by_year"]:
        assert "year" in row
        assert "new_sufferers" in row
        assert "cause_breakdown_suppressed" in row
        assert "type_breakdown_suppressed" in row


async def test_r6_year_2020_not_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """Year 2020 has 12 sufferers (>=10) → breakdown NOT suppressed."""
    result = await r6_trends.run(db_session)
    row_2020 = next(r for r in result["by_year"] if r["year"] == 2020)

    assert row_2020["new_sufferers"] == 12
    assert row_2020["cause_breakdown_suppressed"] is False
    assert row_2020["type_breakdown_suppressed"] is False
    # Breakdown dicts should be present
    assert "cause_breakdown" in row_2020
    assert "leak_type_breakdown" in row_2020


async def test_r6_year_2021_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """Year 2021 has 9 sufferers (<10) → breakdown suppressed."""
    result = await r6_trends.run(db_session)
    row_2021 = next(r for r in result["by_year"] if r["year"] == 2021)

    assert row_2021["new_sufferers"] == 9
    assert row_2021["cause_breakdown_suppressed"] is True
    assert row_2021["type_breakdown_suppressed"] is True
    # Breakdown dicts should NOT be present
    assert "cause_breakdown" not in row_2021
    assert "leak_type_breakdown" not in row_2021


async def test_r6_year_2020_cause_breakdown_content(db_session: AsyncSession, standard_cohort: dict):
    """Year 2020 (England, all EDS): CTD group should show count=12."""
    result = await r6_trends.run(db_session)
    row_2020 = next(r for r in result["by_year"] if r["year"] == 2020)

    ctd = row_2020["cause_breakdown"].get("Connective Tissue Disorder")
    assert ctd is not None
    assert ctd["suppressed"] is False
    assert ctd["count"] == 12


# ── Filter smoke tests ────────────────────────────────────────────────────────

async def test_r6_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    # Only England sufferers: year 2020 only
    assert result["year_range"]["distinct_years"] == 1
    assert result["year_range"]["first_year"] == 2020


async def test_r6_filter_diagnostic_status(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session, diagnostic_status="csfLeakSuffererDiagnosed")

    assert result["filters_applied"]["diagnostic_status"] == "csfLeakSuffererDiagnosed"
    # England (12) + France (1) = 13 diagnosed
    assert isinstance(result["by_year"], list)


async def test_r6_filter_cause_group(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session, cause_group="Iatrogenic")

    assert result["filters_applied"]["cause_group"] == "Iatrogenic"
    assert isinstance(result["by_year"], list)


async def test_r6_filter_leak_type(db_session: AsyncSession, standard_cohort: dict):
    result = await r6_trends.run(db_session, leak_type="spinal")

    assert result["filters_applied"]["leak_type"] == "spinal"
    # Only England has spinal — year 2020 only
    assert result["year_range"]["distinct_years"] == 1


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r6_empty_cohort(db_session: AsyncSession):
    """No data in DB — trend_charts_available=False, by_year=[]."""
    result = await r6_trends.run(db_session, country="Atlantis")

    assert result["trend_charts_available"] is False
    assert result["by_year"] == []
    assert result["year_range"]["distinct_years"] == 0
    assert result["year_range"]["first_year"] is None
    assert result["year_range"]["last_year"] is None
    assert result["trend_charts_note"] is not None
