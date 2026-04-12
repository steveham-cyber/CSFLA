"""
Integration tests for Report 1 — Cohort Overview.

R1 takes no filters and always represents the full cohort.
Tests:
  1. Happy path — correct keys, types, no errors
  2. k≥10 suppression — countries below threshold absent from shown list
  3. Empty cohort — returns gracefully with zeros, not exceptions
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r1_cohort


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r1_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r1_cohort.run(db_session)

    # Top-level keys present
    assert "total_members" in result
    assert "status_breakdown" in result
    assert "sufferer_summary" in result
    assert "supporter_summary" in result
    assert "country_breakdown" in result
    assert "data_completeness" in result

    # total_members is a non-negative int
    assert isinstance(result["total_members"], int)
    assert result["total_members"] >= 0

    # status_breakdown is a list of dicts with required keys
    for entry in result["status_breakdown"]:
        assert "status" in entry
        assert "count" in entry
        assert "pct_of_total" in entry

    # sufferer_summary structure
    ss = result["sufferer_summary"]
    assert "total_sufferers" in ss
    assert "active_sufferers" in ss
    assert "diagnosed" in ss
    assert "suspected" in ss
    assert "former" in ss

    # country_breakdown structure
    cb = result["country_breakdown"]
    assert "shown" in cb
    assert "suppressed_member_count" in cb
    assert isinstance(cb["shown"], list)
    assert isinstance(cb["suppressed_member_count"], int)

    # data_completeness structure
    dc = result["data_completeness"]
    for key in ("gender", "age_band", "leak_type", "cause_of_leak"):
        assert key in dc
        assert "count" in dc[key]
        assert "pct" in dc[key]


async def test_r1_total_members_matches_seed(db_session: AsyncSession, standard_cohort: dict):
    result = await r1_cohort.run(db_session)
    assert result["total_members"] == standard_cohort["total"]


async def test_r1_sufferer_counts_correct(db_session: AsyncSession, standard_cohort: dict):
    result = await r1_cohort.run(db_session)
    ss = result["sufferer_summary"]

    # 13 diagnosed (12 England + 1 France) + 9 suspected + 2 former = 24 sufferers
    assert ss["total_sufferers"] == 24
    # active = diagnosed + suspected = 13 + 9 = 22
    assert ss["active_sufferers"]["count"] == 22
    assert ss["diagnosed"]["count"] == 13
    assert ss["suspected"]["count"] == 9
    assert ss["former"]["count"] == 2


# ── k≥10 suppression ─────────────────────────────────────────────────────────
# R1 uses SQL HAVING COUNT(*) >= min_c — suppressed countries are simply absent.

async def test_r1_country_suppression(db_session: AsyncSession, standard_cohort: dict):
    result = await r1_cohort.run(db_session)
    cb = result["country_breakdown"]
    shown_countries = {row["country"] for row in cb["shown"]}

    # England has 12 members — must be shown
    assert "England" in shown_countries

    # Germany has 2 members, France has 1 — both below k=10, absent from shown
    assert "Germany" not in shown_countries
    assert "France" not in shown_countries

    # Scotland has 9 members — below k=10, absent
    assert "Scotland" not in shown_countries

    # suppressed_member_count captures the hidden members
    assert cb["suppressed_member_count"] > 0


async def test_r1_country_shown_counts_add_up(db_session: AsyncSession, standard_cohort: dict):
    result = await r1_cohort.run(db_session)
    cb = result["country_breakdown"]
    shown_total = sum(row["count"] for row in cb["shown"])
    assert shown_total + cb["suppressed_member_count"] == result["total_members"]


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r1_empty_cohort(db_session: AsyncSession):
    """No data in DB — R1 should return zeros, not raise exceptions."""
    result = await r1_cohort.run(db_session)

    assert result["total_members"] == 0
    assert result["status_breakdown"] == []
    assert result["sufferer_summary"]["total_sufferers"] == 0
    assert result["country_breakdown"]["shown"] == []
    assert result["country_breakdown"]["suppressed_member_count"] == 0
    assert result["data_completeness"]["gender"]["count"] == 0
