"""
UI page routes — serves Jinja2 HTML templates.

These routes render HTML pages. Report data is loaded client-side via fetch
to the existing /api/reports/* JSON endpoints.

Authentication: all routes require a valid session. Unauthenticated requests
are redirected to /auth/login (not given a JSON 401 — these are browser routes).
Admin-only pages return a 403 redirect for researcher/viewer roles.
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from auth.entra import CurrentUser
from api.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ── Auth helper for HTML routes ──────────────────────────────────────────────

def get_ui_user(request: Request) -> CurrentUser | RedirectResponse:
    """
    Returns the current user for HTML routes.
    Unlike the API dependency, unauthenticated requests redirect to /auth/login
    rather than returning a JSON 401.
    """
    user_data = request.session.get("user")
    if not user_data:
        return RedirectResponse(url="/auth/login", status_code=302)
    return CurrentUser(user_data)


def _require_ui_user(request: Request):
    result = get_ui_user(request)
    if isinstance(result, RedirectResponse):
        return result
    return result


def _require_ui_admin(request: Request):
    result = get_ui_user(request)
    if isinstance(result, RedirectResponse):
        return result
    if not result.has_role("admin"):
        return RedirectResponse(url="/dashboard", status_code=302)
    return result


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request):
    user = _require_ui_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "active_nav": "dashboard",
        "page_title": "Research Dashboard",
    })


@router.get("/reports", response_class=HTMLResponse, include_in_schema=False)
async def reports_list(request: Request):
    user = _require_ui_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("reports_list.html", {
        "request": request,
        "user": user,
        "active_nav": "reports",
        "page_title": "Standard Reports",
    })


@router.get("/reports/{report_id}", response_class=HTMLResponse, include_in_schema=False)
async def report_view(request: Request, report_id: str):
    user = _require_ui_user(request)
    if isinstance(user, RedirectResponse):
        return user

    # Validate report_id
    valid_ids = {"r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"}
    if report_id not in valid_ids:
        return RedirectResponse(url="/reports", status_code=302)

    return templates.TemplateResponse("report_view.html", {
        "request": request,
        "user": user,
        "active_nav": "reports",
        "report_id": report_id,
        "page_title": f"Report {report_id[1:]}",
    })


@router.get("/ai-analysis", response_class=HTMLResponse, include_in_schema=False)
async def ai_analysis(request: Request):
    user = _require_ui_user(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("ai_analysis.html", {
        "request": request,
        "user": user,
        "active_nav": "ai",
        "page_title": "AI Analysis",
    })


@router.get("/import", response_class=HTMLResponse, include_in_schema=False)
async def import_page(request: Request):
    user = _require_ui_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("import.html", {
        "request": request,
        "user": user,
        "active_nav": "import",
        "page_title": "Data Import",
    })


@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_page(request: Request):
    user = _require_ui_admin(request)
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "active_nav": "admin",
        "page_title": "Administration",
    })
