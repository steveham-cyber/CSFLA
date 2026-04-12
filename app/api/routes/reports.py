"""
Report endpoints — researcher and admin roles.

All queries enforce k>=10 minimum cohort at the report layer.
All endpoints require at least researcher role.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_researcher
from auth.entra import CurrentUser
from db.connection import get_db

import reports.r1_cohort    as r1
import reports.r2_status    as r2
import reports.r3_leak_type as r3
import reports.r4_cause     as r4
import reports.r5_geography as r5
import reports.r6_trends    as r6
import reports.r7_cause_type as r7
import reports.r8_referral  as r8

router = APIRouter()


# ── Report catalogue ──────────────────────────────────────────────────────────

@router.get("/")
async def list_reports(user: CurrentUser = Depends(require_researcher)):
    """Return metadata for all available standard reports."""
    return {
        "reports": [
            {
                "id": "r1",
                "title": "Cohort Overview",
                "path": "/reports/cohort",
                "filters": [],
                "description": "Whole-cohort snapshot: size, status composition, geographic spread, data completeness.",
            },
            {
                "id": "r2",
                "title": "Diagnostic Status Profile",
                "path": "/reports/status",
                "filters": ["country", "gender", "age_band", "year_from", "year_to"],
                "description": "Sufferer status breakdown cross-tabulated with demographics.",
            },
            {
                "id": "r3",
                "title": "CSF Leak Type Distribution",
                "path": "/reports/leak-type",
                "filters": ["diagnostic_status", "country", "gender", "age_band", "year_from", "year_to"],
                "description": "Leak type distribution for sufferers, cross-tabulated with demographics.",
            },
            {
                "id": "r4",
                "title": "Cause of Leak Analysis",
                "path": "/reports/cause",
                "filters": [
                    "cause_group", "individual_cause", "leak_type", "diagnostic_status",
                    "country", "gender", "age_band", "year_from", "year_to",
                ],
                "description": "Cause distribution by clinical grouping, with cross-tabulations.",
            },
            {
                "id": "r5",
                "title": "Geographic Distribution",
                "path": "/reports/geography",
                "filters": ["country_group", "diagnostic_status", "leak_type", "cause_group"],
                "description": "UK and European geographic breakdown with density data.",
            },
            {
                "id": "r6",
                "title": "Membership Growth and Cohort Trends",
                "path": "/reports/trends",
                "filters": ["diagnostic_status", "country", "leak_type", "cause_group"],
                "description": "Time-series metrics across member_since_year.",
            },
            {
                "id": "r7",
                "title": "Cause × Type Cross-Analysis",
                "path": "/reports/cause-type",
                "filters": ["diagnostic_status", "gender", "age_band", "country", "year_from", "year_to"],
                "description": "Research matrix: cause of leak × leak type, with chi-square test.",
            },
            {
                "id": "r8",
                "title": "Referral Source Analysis",
                "path": "/reports/referral",
                "filters": ["year_from", "year_to", "country"],
                "description": "How members heard about the charity.",
            },
        ]
    }


# ── R1: Cohort Overview ───────────────────────────────────────────────────────

@router.get("/cohort")
async def report_cohort(
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 1 — Cohort Overview. No filters."""
    return await r1.run(db)


# ── R2: Diagnostic Status Profile ────────────────────────────────────────────

@router.get("/status")
async def report_status(
    country:   Optional[str] = Query(default=None),
    gender:    Optional[str] = Query(default=None),
    age_band:  Optional[str] = Query(default=None),
    year_from: Optional[int] = Query(default=None, ge=2000, le=2100),
    year_to:   Optional[int] = Query(default=None, ge=2000, le=2100),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 2 — Diagnostic Status Profile."""
    _validate_year_range(year_from, year_to)
    return await r2.run(db, country=country, gender=gender, age_band=age_band,
                        year_from=year_from, year_to=year_to)


# ── R3: CSF Leak Type Distribution ───────────────────────────────────────────

@router.get("/leak-type")
async def report_leak_type(
    diagnostic_status: Optional[str] = Query(default=None),
    country:           Optional[str] = Query(default=None),
    gender:            Optional[str] = Query(default=None),
    age_band:          Optional[str] = Query(default=None),
    year_from:         Optional[int] = Query(default=None, ge=2000, le=2100),
    year_to:           Optional[int] = Query(default=None, ge=2000, le=2100),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 3 — CSF Leak Type Distribution."""
    _validate_year_range(year_from, year_to)
    return await r3.run(
        db,
        diagnostic_status=diagnostic_status,
        country=country,
        gender=gender,
        age_band=age_band,
        year_from=year_from,
        year_to=year_to,
    )


# ── R4: Cause of Leak Analysis ────────────────────────────────────────────────

@router.get("/cause")
async def report_cause(
    cause_group:       Optional[str] = Query(default=None),
    individual_cause:  Optional[str] = Query(default=None),
    leak_type:         Optional[str] = Query(default=None),
    diagnostic_status: Optional[str] = Query(default=None),
    country:           Optional[str] = Query(default=None),
    gender:            Optional[str] = Query(default=None),
    age_band:          Optional[str] = Query(default=None),
    year_from:         Optional[int] = Query(default=None, ge=2000, le=2100),
    year_to:           Optional[int] = Query(default=None, ge=2000, le=2100),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 4 — Cause of Leak Analysis."""
    _validate_year_range(year_from, year_to)
    return await r4.run(
        db,
        cause_group=cause_group,
        individual_cause=individual_cause,
        leak_type=leak_type,
        diagnostic_status=diagnostic_status,
        country=country,
        gender=gender,
        age_band=age_band,
        year_from=year_from,
        year_to=year_to,
    )


# ── R5: Geographic Distribution ───────────────────────────────────────────────

@router.get("/geography")
async def report_geography(
    country_group:     Optional[str] = Query(default=None, pattern="^(uk|europe)$"),
    diagnostic_status: Optional[str] = Query(default=None),
    leak_type:         Optional[str] = Query(default=None),
    cause_group:       Optional[str] = Query(default=None),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 5 — Geographic Distribution."""
    return await r5.run(
        db,
        country_group=country_group,
        diagnostic_status=diagnostic_status,
        leak_type=leak_type,
        cause_group=cause_group,
    )


# ── R6: Membership Growth and Cohort Trends ───────────────────────────────────

@router.get("/trends")
async def report_trends(
    diagnostic_status: Optional[str] = Query(default=None),
    country:           Optional[str] = Query(default=None),
    leak_type:         Optional[str] = Query(default=None),
    cause_group:       Optional[str] = Query(default=None),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 6 — Membership Growth and Cohort Trends."""
    return await r6.run(
        db,
        diagnostic_status=diagnostic_status,
        country=country,
        leak_type=leak_type,
        cause_group=cause_group,
    )


# ── R7: Cause × Type Cross-Analysis ──────────────────────────────────────────

@router.get("/cause-type")
async def report_cause_type(
    diagnostic_status: Optional[str] = Query(default=None),
    gender:            Optional[str] = Query(default=None),
    age_band:          Optional[str] = Query(default=None),
    country:           Optional[str] = Query(default=None),
    year_from:         Optional[int] = Query(default=None, ge=2000, le=2100),
    year_to:           Optional[int] = Query(default=None, ge=2000, le=2100),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 7 — Cause × Type Cross-Analysis with chi-square test."""
    _validate_year_range(year_from, year_to)
    return await r7.run(
        db,
        diagnostic_status=diagnostic_status,
        gender=gender,
        age_band=age_band,
        country=country,
        year_from=year_from,
        year_to=year_to,
    )


# ── R8: Referral Source Analysis ──────────────────────────────────────────────

@router.get("/referral")
async def report_referral(
    year_from: Optional[int] = Query(default=None, ge=2000, le=2100),
    year_to:   Optional[int] = Query(default=None, ge=2000, le=2100),
    country:   Optional[str] = Query(default=None),
    user: CurrentUser = Depends(require_researcher),
    db: AsyncSession = Depends(get_db),
):
    """Report 8 — Referral Source Analysis."""
    _validate_year_range(year_from, year_to)
    return await r8.run(db, year_from=year_from, year_to=year_to, country=country)


# ── Validation helpers ────────────────────────────────────────────────────────

def _validate_year_range(year_from: Optional[int], year_to: Optional[int]) -> None:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year_from must be less than or equal to year_to.",
        )
