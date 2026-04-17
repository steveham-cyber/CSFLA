"""
Integration tests for Report 7 — Cause x Type Cross-Analysis.

Fixture summary (from standard_cohort):
  England  12  EDS (CTD group)             × spinal
  Scotland  9  lumbarPuncture (Iatrogenic) × cranial
  Germany   2  trauma (Traumatic)          × spinalAndCranial
             + spinalSurgery (Iatrogenic)  × spinalAndCranial  (both causes per member)
  France    1  spinalSurgery (Iatrogenic)  × unknown

Chi-square contingency table (excludes Unknown/Not disclosed group, excludes unknown type):
           spinal  cranial  spinalAndCranial
CTD            12        0                0
Iatrogenic      0        9                2    (Scotland×cranial + Germany×spinalAndCranial)
Traumatic       0        0                2    (Germany×spinalAndCranial)

Valid 3x3 table — chi-square should compute (cells_with_expected_below_5 > 0).

Tests:
  1. Happy path — correct structure, no errors
  2. Matrix rows: group and individual types present
  3. Cell values: CTD×spinal not suppressed (12), Traumatic×all suppressed (<10)
  4. Chi-square: valid=True, correct fields present
  5. Chi-square degenerate: empty cohort returns valid=False gracefully
  6. Filter smoke tests
"""

from sqlalchemy.ext.asyncio import AsyncSession

from reports import r7_cause_type


# ── Happy path ────────────────────────────────────────────────────────────────

async def test_r7_happy_path_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)

    assert "filters_applied" in result
    assert "leak_type_columns" in result
    assert "matrix" in result
    assert "denominator_note" in result
    assert "chi_square_test" in result

    assert isinstance(result["leak_type_columns"], list)
    assert isinstance(result["matrix"], list)
    assert len(result["matrix"]) > 0


async def test_r7_leak_type_columns(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    # LEAK_TYPE_ORDER: spinal, cranial, spinalAndCranial, unknown
    assert result["leak_type_columns"] == ["spinal", "cranial", "spinalAndCranial", "unknown"]


# ── Matrix structure ──────────────────────────────────────────────────────────

async def test_r7_matrix_has_all_cause_groups(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    group_labels = {r["label"] for r in result["matrix"] if r["type"] == "group"}
    assert "Iatrogenic" in group_labels
    assert "Connective Tissue Disorder" in group_labels
    assert "Spontaneous / Structural (Spinal)" in group_labels
    assert "Traumatic" in group_labels
    assert "Unknown / Not disclosed" in group_labels


async def test_r7_matrix_has_individual_rows(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    individual_labels = {r["label"] for r in result["matrix"] if r["type"] == "individual"}
    # Causes that have members: ehlersDanlosSyndrome, lumbarPuncture, trauma, spinalSurgery
    assert "ehlersDanlosSyndrome" in individual_labels
    assert "lumbarPuncture" in individual_labels
    assert "trauma" in individual_labels
    assert "spinalSurgery" in individual_labels


async def test_r7_matrix_group_row_has_required_keys(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    group_row = next(r for r in result["matrix"] if r["type"] == "group")
    assert "label" in group_row
    assert "total" in group_row
    assert "row_total" in group_row
    for lt in ("spinal", "cranial", "spinalAndCranial", "unknown"):
        assert lt in group_row
        assert "suppressed" in group_row[lt]


async def test_r7_matrix_individual_row_has_pct_of_row(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    ind_row = next(r for r in result["matrix"] if r["type"] == "individual")
    assert "pct_of_row" in ind_row
    assert isinstance(ind_row["pct_of_row"], dict)


# ── Cell suppression ──────────────────────────────────────────────────────────

async def test_r7_ctd_spinal_not_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """CTD group × spinal: 12 members (>=10) → not suppressed."""
    result = await r7_cause_type.run(db_session)
    ctd_row = next(
        r for r in result["matrix"]
        if r["type"] == "group" and r["label"] == "Connective Tissue Disorder"
    )
    assert ctd_row["spinal"]["suppressed"] is False
    assert ctd_row["spinal"]["count"] == 12


async def test_r7_iatrogenic_cranial_not_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """Iatrogenic × cranial: 9 members (<10) → suppressed."""
    result = await r7_cause_type.run(db_session)
    iatro_row = next(
        r for r in result["matrix"]
        if r["type"] == "group" and r["label"] == "Iatrogenic"
    )
    # Scotland (9 members) has lumbarPuncture (Iatrogenic) × cranial
    assert iatro_row["cranial"]["suppressed"] is True


async def test_r7_traumatic_all_cells_suppressed(db_session: AsyncSession, standard_cohort: dict):
    """Traumatic has 2 members total — all cells must be suppressed."""
    result = await r7_cause_type.run(db_session)
    traumatic_row = next(
        r for r in result["matrix"]
        if r["type"] == "group" and r["label"] == "Traumatic"
    )
    for lt in ("spinal", "cranial", "spinalAndCranial", "unknown"):
        assert traumatic_row[lt]["suppressed"] is True, (
            f"Traumatic × {lt} should be suppressed"
        )


# ── Chi-square ────────────────────────────────────────────────────────────────

async def test_r7_chi_square_structure(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session)
    chi = result["chi_square_test"]
    assert "valid" in chi
    assert "note" in chi


async def test_r7_chi_square_valid(db_session: AsyncSession, standard_cohort: dict):
    """
    3 cause groups × 3 leak types (after excluding Unknown/unknown) —
    contingency table is valid and chi-square should compute.
    """
    result = await r7_cause_type.run(db_session)
    chi = result["chi_square_test"]

    assert chi["valid"] is True
    assert "chi2" in chi
    assert "p_value" in chi
    assert "degrees_of_freedom" in chi
    assert "cells_with_expected_below_5" in chi
    assert isinstance(chi["chi2"], float)
    assert isinstance(chi["p_value"], float)


async def test_r7_chi_square_degenerate_empty_cohort(db_session: AsyncSession):
    """Empty cohort → degenerate table → chi_square_test valid=False."""
    result = await r7_cause_type.run(db_session)
    chi = result["chi_square_test"]
    assert chi["valid"] is False


# ── Filter smoke tests ────────────────────────────────────────────────────────

async def test_r7_filter_diagnostic_status(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session, diagnostic_status="csfLeakSuffererDiagnosed")

    assert result["filters_applied"]["diagnostic_status"] == "csfLeakSuffererDiagnosed"
    assert isinstance(result["matrix"], list)


async def test_r7_filter_gender(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session, gender="female")

    assert result["filters_applied"]["gender"] == "female"
    # Female sufferers: England 12 + Germany 2 + France 1 = 15
    assert isinstance(result["matrix"], list)


async def test_r7_filter_country(db_session: AsyncSession, standard_cohort: dict):
    result = await r7_cause_type.run(db_session, country="England")

    assert result["filters_applied"]["country"] == "England"
    # Only England: CTD × spinal = 12
    ctd_row = next(
        r for r in result["matrix"]
        if r["type"] == "group" and r["label"] == "Connective Tissue Disorder"
    )
    assert ctd_row["spinal"]["count"] == 12


async def test_r7_empty_cohort_no_crash(db_session: AsyncSession):
    """Impossible filter → empty matrix with valid=False chi-square, no exceptions."""
    result = await r7_cause_type.run(db_session, country="Atlantis")

    assert isinstance(result["matrix"], list)
    # All group rows should be present (from CAUSE_GROUP_ORDER iteration)
    group_labels = {r["label"] for r in result["matrix"] if r["type"] == "group"}
    assert len(group_labels) == 5

    chi = result["chi_square_test"]
    assert chi["valid"] is False
