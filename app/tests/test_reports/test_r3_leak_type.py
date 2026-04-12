"""
Integration tests for Report 3 — CSF Leak Type Distribution.

Tests:
  1. Happy path — correct keys, types, no errors
  2. k≥10 suppression — cross-tab cells below threshold show suppressed marker
  3. Filter smoke test — diagnostic_status filter applied and reflected
  4. Empty cohort — impossible filter returns gracefully
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r3_leak_type


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r3_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session)

    assert "filters_applied" in result
    assert "primary" in result
    assert "by_status" in result
    assert "by_age_band" in result
    assert "by_gender" in result
    assert "by_country" in result
    assert "by_year" in result

    primary = result["primary"]
    assert "total_sufferers_with_type" in primary
    assert "known_type_total" in primary
    assert "unknown_rate_pct" in primary
    assert "breakdown" in primary
    assert isinstance(primary["breakdown"], list)

    for entry in primary["breakdown"]:
        assert "leak_type" in entry
        assert "count" in entry
        assert "pct_of_sufferers_with_type" in entry


async def test_r3_leak_type_counts(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session)
    primary = result["primary"]

    # Sufferers with any leak type (excluding notRelevant):
    # 12 spinal + 9 cranial + 2 spinalAndCranial + 1 unknown = 24
    # But total_sufferers_with_type counts DISTINCT members per leak type query
    # (a member can appear in multiple types — but our seed gives 1 type each)
    assert primary["total_sufferers_with_type"] == 24

    # known_type_total excludes 'unknown' (1 France member)
    assert primary["known_type_total"] == 23


async def test_r3_by_status_is_list(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session)
    assert isinstance(result["by_status"], list)
    assert len(result["by_status"]) > 0


async def test_r3_cross_tabs_are_lists(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session)
    for key in ("by_age_band", "by_gender", "by_country", "by_year"):
        assert isinstance(result[key], list), f"{key} should be a list"


# ── k≥10 suppression ─────────────────────────────────────────────────────────

async def test_r3_suppression_in_cross_tab(db_session: AsyncSession, standard_cohort: dict):
    """
    In by_country cross-tab:
    - England (12 members) — total cell not suppressed
    - Scotland (9 members) — total cell suppressed
    """
    result = await r3_leak_type.run(db_session)
    by_country = result["by_country"]

    england_row = next((r for r in by_country if r["value"] == "England"), None)
    scotland_row = next((r for r in by_country if r["value"] == "Scotland"), None)

    assert england_row is not None
    assert scotland_row is not None

    assert england_row["total"]["suppressed"] is False
    assert england_row["total"]["count"] == 12

    assert scotland_row["total"]["suppressed"] is True
    assert scotland_row["total"]["count"] is None


# ── Filter smoke test ─────────────────────────────────────────────────────────

async def test_r3_filter_diagnostic_status(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session, diagnostic_status="csfLeakSuffererDiagnosed")

    assert result["filters_applied"]["diagnostic_status"] == "csfLeakSuffererDiagnosed"
    # Only diagnosed members: 12 England + 1 France = 13
    assert result["primary"]["total_sufferers_with_type"] == 13


async def test_r3_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    assert result["primary"]["total_sufferers_with_type"] == 12


async def test_r3_filter_gender(db_session: AsyncSession, standard_cohort: dict):
    result = await r3_leak_type.run(db_session, gender="male")

    assert result["filters_applied"]["gender"] == "male"
    # Only male sufferers: 9 Scotland
    assert result["primary"]["total_sufferers_with_type"] == 9


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r3_empty_cohort(db_session: AsyncSession):
    result = await r3_leak_type.run(db_session, country="Atlantis")

    assert result["filters_applied"]["country"] == "Atlantis"
    assert result["primary"]["total_sufferers_with_type"] == 0
    assert result["primary"]["breakdown"] == []
    assert result["by_status"] == []
    assert result["by_country"] == []
    assert result["by_gender"] == []
