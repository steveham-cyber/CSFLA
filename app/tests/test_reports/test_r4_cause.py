"""
Integration tests for Report 4 — Cause of Leak Analysis.

Fixture summary (from standard_cohort):
  England  12  cause: ehlersDanlosSyndrome  (Connective Tissue Disorder)
  Scotland  9  cause: lumbarPuncture        (Iatrogenic)
  Germany   2  causes: trauma (Traumatic) + spinalSurgery (Iatrogenic) — 2 per member
  France    1  cause: spinalSurgery         (Iatrogenic)

Cause group totals (COUNT DISTINCT members with >=1 cause in that group):
  Iatrogenic:               12  (9 Scotland + 2 Germany + 1 France)
  Connective Tissue Disorder: 12  (12 England)
  Traumatic:                 2  (2 Germany)
  Unknown/Not disclosed:     0

Tests:
  1. Happy path — correct structure, no errors
  2. Cause group counts correct
  3. k>=10 suppression in crosstab matrices
  4. Filter smoke tests (cause_group, individual_cause)
  5. Empty cohort — graceful zero result
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r4_cause


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r4_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session)

    assert "filters_applied" in result
    assert "primary" in result
    assert "crosstab_leak_type" in result
    assert "by_status" in result
    assert "by_age_band" in result
    assert "by_gender" in result
    assert "by_country" in result
    assert "by_year" in result

    primary = result["primary"]
    assert "total_members_with_cause" in primary
    assert "denominator_note" in primary
    assert "cause_groups" in primary
    assert isinstance(primary["cause_groups"], list)

    for cg in primary["cause_groups"]:
        assert "cause_group" in cg
        assert "count" in cg
        assert "pct_of_total_with_cause" in cg
        assert "individual_causes" in cg
        assert isinstance(cg["individual_causes"], list)


async def test_r4_total_members_with_cause(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session)
    # All 24 members have at least one cause
    assert result["primary"]["total_members_with_cause"] == 24


async def test_r4_iatrogenic_count(db_session: AsyncSession, standard_cohort: dict):
    """Iatrogenic = 9 Scotland (lumbarPuncture) + 2 Germany + 1 France (spinalSurgery) = 12."""
    result = await r4_cause.run(db_session)
    iatrogenic = next(
        g for g in result["primary"]["cause_groups"]
        if g["cause_group"] == "Iatrogenic"
    )
    assert iatrogenic["count"] == 12


async def test_r4_ctd_count(db_session: AsyncSession, standard_cohort: dict):
    """Connective Tissue Disorder = 12 England (ehlersDanlosSyndrome)."""
    result = await r4_cause.run(db_session)
    ctd = next(
        g for g in result["primary"]["cause_groups"]
        if g["cause_group"] == "Connective Tissue Disorder"
    )
    assert ctd["count"] == 12


async def test_r4_traumatic_count(db_session: AsyncSession, standard_cohort: dict):
    """Traumatic = 2 Germany (trauma)."""
    result = await r4_cause.run(db_session)
    traumatic = next(
        g for g in result["primary"]["cause_groups"]
        if g["cause_group"] == "Traumatic"
    )
    assert traumatic["count"] == 2


async def test_r4_individual_cause_drilldown(db_session: AsyncSession, standard_cohort: dict):
    """lumbarPuncture appears under Iatrogenic with count 9."""
    result = await r4_cause.run(db_session)
    iatrogenic = next(
        g for g in result["primary"]["cause_groups"]
        if g["cause_group"] == "Iatrogenic"
    )
    lp = next(
        (c for c in iatrogenic["individual_causes"] if c["cause"] == "lumbarPuncture"),
        None,
    )
    assert lp is not None
    assert lp["count"] == 9


# ── k>=10 suppression ─────────────────────────────────────────────────────────
# R4 applies cell() to cross-tab cells — suppressed if count < 10.

async def test_r4_crosstab_spinal_iatrogenic_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """
    In the cause × leak type cross-tab:
    - Iatrogenic × spinal: 0 (lumbarPuncture × cranial, not spinal) → suppressed
    - CTD × spinal: 12 → not suppressed
    """
    result = await r4_cause.run(db_session)
    matrix = result["crosstab_leak_type"]["matrix"]

    ctd_row = next(r for r in matrix if r["cause_group"] == "Connective Tissue Disorder")
    assert ctd_row["spinal"]["suppressed"] is False
    assert ctd_row["spinal"]["count"] == 12

    iatrogenic_row = next(r for r in matrix if r["cause_group"] == "Iatrogenic")
    # Iatrogenic members have cranial (Scotland) and spinalAndCranial (Germany/France=unknown)
    # Iatrogenic × spinal: 0 → suppressed
    assert iatrogenic_row["spinal"]["suppressed"] is True


async def test_r4_crosstab_traumatic_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """Traumatic has 2 members — all cells in that row suppressed."""
    result = await r4_cause.run(db_session)
    matrix = result["crosstab_leak_type"]["matrix"]

    traumatic_row = next(r for r in matrix if r["cause_group"] == "Traumatic")
    for lt_key in ("spinal", "cranial", "spinalAndCranial", "unknown"):
        assert traumatic_row[lt_key]["suppressed"] is True, (
            f"Traumatic × {lt_key} should be suppressed (count < 10)"
        )


# ── Filter smoke tests ────────────────────────────────────────────────────────

async def test_r4_filter_cause_group_iatrogenic(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session, cause_group="Iatrogenic")

    assert result["filters_applied"]["cause_group"] == "Iatrogenic"
    # Scoped to Iatrogenic members only: 9 Scotland + 2 Germany + 1 France = 12
    assert result["primary"]["total_members_with_cause"] == 12


async def test_r4_filter_individual_cause(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session, individual_cause="lumbarPuncture")

    assert result["filters_applied"]["individual_cause"] == "lumbarPuncture"
    # Only Scotland has lumbarPuncture: 9 members
    assert result["primary"]["total_members_with_cause"] == 9


async def test_r4_filter_leak_type(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session, leak_type="spinal")

    assert result["filters_applied"]["leak_type"] == "spinal"
    # Only England has spinal leak type: 12 members, all with EDS
    assert result["primary"]["total_members_with_cause"] == 12


async def test_r4_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r4_cause.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    assert result["primary"]["total_members_with_cause"] == 12


# ── Empty cohort ──────────────────────────────────────────────────────────────

async def test_r4_empty_cohort(db_session: AsyncSession):
    result = await r4_cause.run(db_session, country="Atlantis")

    assert result["primary"]["total_members_with_cause"] == 0
    for cg in result["primary"]["cause_groups"]:
        assert cg["count"] == 0
        assert cg["individual_causes"] == []
