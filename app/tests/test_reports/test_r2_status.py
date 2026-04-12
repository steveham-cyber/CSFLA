"""
Integration tests for Report 2 — Diagnostic Status Profile.

Tests:
  1. Happy path — correct keys, types, no errors
  2. k≥10 suppression — cross-tab cells below threshold show suppressed marker
  3. Filter smoke test — country filter returns without error, filters_applied matches
  4. Empty cohort — impossible filter returns gracefully
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r2_status


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r2_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session)

    assert "filters_applied" in result
    assert "primary" in result
    assert "by_age_band" in result
    assert "by_gender" in result
    assert "by_country" in result
    assert "by_region" in result
    assert "by_year" in result

    primary = result["primary"]
    assert "total_sufferers" in primary
    assert "pct_diagnosed_of_active" in primary
    assert "breakdown" in primary
    assert isinstance(primary["breakdown"], list)

    for entry in primary["breakdown"]:
        assert "status" in entry
        assert "count" in entry
        assert "pct_of_sufferers" in entry


async def test_r2_total_sufferers_correct(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session)
    # 13 diagnosed (12 England + 1 France) + 9 suspected + 2 former = 24
    assert result["primary"]["total_sufferers"] == 24


async def test_r2_cross_tabs_are_lists(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session)
    for key in ("by_age_band", "by_gender", "by_country", "by_region", "by_year"):
        assert isinstance(result[key], list), f"{key} should be a list"


# ── k≥10 suppression ─────────────────────────────────────────────────────────
# R2 uses cell() helper — suppressed groups show {"count": null, "suppressed": true}.

async def test_r2_suppression_in_cross_tab(db_session: AsyncSession, standard_cohort: dict):
    """
    Scotland has 9 sufferers — below k=10.
    In by_country cross-tab, Scotland's total cell should be suppressed.
    England has 12 sufferers — should not be suppressed.
    """
    result = await r2_status.run(db_session)
    by_country = result["by_country"]

    england_row = next((r for r in by_country if r["value"] == "England"), None)
    scotland_row = next((r for r in by_country if r["value"] == "Scotland"), None)

    assert england_row is not None, "England should appear in by_country"
    assert scotland_row is not None, "Scotland should appear in by_country"

    # England's total >= 10 — not suppressed
    assert england_row["total"]["suppressed"] is False
    assert england_row["total"]["count"] == 12

    # Scotland's total == 9 — suppressed
    assert scotland_row["total"]["suppressed"] is True
    assert scotland_row["total"]["count"] is None


# ── Filter smoke test ─────────────────────────────────────────────────────────

async def test_r2_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    assert result["filters_applied"]["gender"] is None
    assert isinstance(result["primary"]["breakdown"], list)
    # Filtering to England only — all sufferers there are diagnosed
    assert result["primary"]["total_sufferers"] == 12


async def test_r2_filter_gender(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session, gender="female")

    assert result["filters_applied"]["gender"] == "female"
    # Only female sufferers: 12 England + 2 Germany + 1 France = 15
    assert result["primary"]["total_sufferers"] == 15


async def test_r2_filter_year_range(db_session: AsyncSession, standard_cohort: dict):
    result = await r2_status.run(db_session, year_from=2020, year_to=2021)

    assert result["filters_applied"]["year_from"] == 2020
    assert result["filters_applied"]["year_to"] == 2021
    # Should not raise; total_sufferers >= 0
    assert result["primary"]["total_sufferers"] >= 0


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r2_empty_cohort(db_session: AsyncSession):
    """Impossible filter produces zero-row result without exceptions."""
    result = await r2_status.run(db_session, country="Atlantis")

    assert result["filters_applied"]["country"] == "Atlantis"
    assert result["primary"]["total_sufferers"] == 0
    assert result["primary"]["breakdown"] == []
    assert result["by_age_band"] == []
    assert result["by_gender"] == []
    assert result["by_country"] == []
