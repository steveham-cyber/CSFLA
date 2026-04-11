"""
Report endpoints — researcher and admin roles.
Implementation pending Nova's report specifications.
All queries enforce k>=10 minimum cohort at the service layer.
"""

from fastapi import APIRouter, Depends

from api.dependencies import require_researcher
from auth.entra import CurrentUser

router = APIRouter()

MIN_COHORT_SIZE = 10  # Enforced at query layer — never expose data for groups < 10


@router.get("/standard/{report_id}")
async def get_standard_report(
    report_id: str,
    user: CurrentUser = Depends(require_researcher),
):
    # Stub — standard report engine pending Nova's specifications
    return {"report_id": report_id, "status": "not_yet_implemented"}


@router.get("/")
async def list_reports(user: CurrentUser = Depends(require_researcher)):
    return {"reports": []}
