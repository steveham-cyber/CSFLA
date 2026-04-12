"""
Integration tests for Report 8 — Referral Source Analysis.

Fixture summary (from standard_cohort):
  England  12  referral: ["socialMedia"]
  Scotland  9  referral: ["gp"]
  Germany   2  referral: None (NULL)
  France    1  referral: None (NULL)

Referral source counts:
  socialMedia: 12 members (>=10 → shown in primary.breakdown)
  gp:           9 members (<10  → HAVING-filtered, absent from primary.breakdown)
  null:         3 members (Germany 2 + France 1 → counted as total_members_null_source)

Tests:
  1. Happy path — correct structure, no errors
  2. socialMedia shown (12 members >=10)
  3. gp suppressed by HAVING (<10 members)
  4. null_count correct (3)
  5. by_year cross-tab: socialMedia in 2020 (12 members)
  6. Year range filter: year_from=2021 scopes to Scotland/Germany/France
     → gp (9) still < 10 after filter, stays suppressed
  7. Empty cohort — graceful zero result
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r8_referral


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r8_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session)

    assert "filters_applied" in result
    assert "primary" in result
    assert "by_year" in result
    assert "shown_sources" in result

    primary = result["primary"]
    assert "total_members_with_source" in primary
    assert "total_members_null_source" in primary
    assert "null_note" in primary
    assert "denominator_note" in primary
    assert "breakdown" in primary
    assert isinstance(primary["breakdown"], list)

    for entry in primary["breakdown"]:
        assert "source" in entry
        assert "count" in entry
        assert "pct_of_members_with_source" in entry


async def test_r8_total_members_with_source(db_session: AsyncSession, standard_cohort: dict):
    """12 England (socialMedia) + 9 Scotland (gp) = 21 members with a referral source."""
    result = await r8_referral.run(db_session)
    assert result["primary"]["total_members_with_source"] == 21


# ── Referral source shown / suppressed ───────────────────────────────────────

async def test_r8_social_media_shown(db_session: AsyncSession, standard_cohort: dict):
    """socialMedia has 12 members (>=10) → appears in primary.breakdown."""
    result = await r8_referral.run(db_session)
    sources = {r["source"] for r in result["primary"]["breakdown"]}
    assert "socialMedia" in sources


async def test_r8_social_media_count(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session)
    sm = next(r for r in result["primary"]["breakdown"] if r["source"] == "socialMedia")
    assert sm["count"] == 12


async def test_r8_gp_suppressed_by_having(db_session: AsyncSession, standard_cohort: dict):
    """gp has 9 members (<10) — SQL HAVING filters it; it must not appear in breakdown."""
    result = await r8_referral.run(db_session)
    sources = {r["source"] for r in result["primary"]["breakdown"]}
    assert "gp" not in sources


async def test_r8_shown_sources_matches_breakdown(db_session: AsyncSession, standard_cohort: dict):
    """shown_sources list matches the sources that appear in primary.breakdown."""
    result = await r8_referral.run(db_session)
    breakdown_sources = {r["source"] for r in result["primary"]["breakdown"]}
    shown_set = set(result["shown_sources"])
    assert breakdown_sources == shown_set


# ── NULL referral_source ──────────────────────────────────────────────────────

async def test_r8_null_count(db_session: AsyncSession, standard_cohort: dict):
    """Germany (2) + France (1) have NULL referral_source → null_count=3."""
    result = await r8_referral.run(db_session)
    assert result["primary"]["total_members_null_source"] == 3


# ── by_year cross-tab ─────────────────────────────────────────────────────────

async def test_r8_by_year_is_list(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session)
    assert isinstance(result["by_year"], list)
    assert len(result["by_year"]) > 0


async def test_r8_by_year_row_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session)
    for row in result["by_year"]:
        assert "year" in row
        # Each row should have a key per shown_source
        for source in result["shown_sources"]:
            assert source in row
            assert "suppressed" in row[source]


async def test_r8_by_year_social_media_in_2020(db_session: AsyncSession, standard_cohort: dict):
    """
    England (12 socialMedia members) joined in year 2020.
    In by_year, the 2020 row should have socialMedia with count=12 (not suppressed).
    """
    result = await r8_referral.run(db_session)
    row_2020 = next((r for r in result["by_year"] if r["year"] == 2020), None)
    assert row_2020 is not None
    assert row_2020["socialMedia"]["suppressed"] is False
    assert row_2020["socialMedia"]["count"] == 12


# ── Filter smoke tests ────────────────────────────────────────────────────────

async def test_r8_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    # England only: socialMedia (12) shown
    sources = {r["source"] for r in result["primary"]["breakdown"]}
    assert "socialMedia" in sources
    assert result["primary"]["total_members_null_source"] == 0


async def test_r8_filter_year_from_to_suppresses_all(db_session: AsyncSession, standard_cohort: dict):
    """
    Filter to year 2021 only: Scotland (9, gp) — gp still < 10 → suppressed.
    null members in 2021: 0 (Germany=2022, France=2023).
    """
    result = await r8_referral.run(db_session, year_from=2021, year_to=2021)

    assert result["filters_applied"]["year_from"] == 2021
    assert result["filters_applied"]["year_to"] == 2021
    # gp has 9 members in 2021 — still < 10 → not in breakdown
    sources = {r["source"] for r in result["primary"]["breakdown"]}
    assert "gp" not in sources
    assert result["primary"]["total_members_null_source"] == 0


async def test_r8_filters_applied_reflects_input(db_session: AsyncSession, standard_cohort: dict):
    result = await r8_referral.run(db_session, year_from=2020, year_to=2022, country="England")
    fa = result["filters_applied"]
    assert fa["year_from"] == 2020
    assert fa["year_to"] == 2022
    assert fa["country"] == "England"


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r8_empty_cohort(db_session: AsyncSession):
    result = await r8_referral.run(db_session, country="Atlantis")

    assert result["primary"]["total_members_with_source"] == 0
    assert result["primary"]["total_members_null_source"] == 0
    assert result["primary"]["breakdown"] == []
    assert result["by_year"] == []
    assert result["shown_sources"] == []
