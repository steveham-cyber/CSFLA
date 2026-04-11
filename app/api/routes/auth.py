import secrets
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from auth.entra import get_auth_url, exchange_code_for_token

router = APIRouter()


@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    redirect_uri = str(request.url_for("callback"))
    return RedirectResponse(get_auth_url(redirect_uri=redirect_uri, state=state))


@router.get("/callback")
async def callback(request: Request, code: str, state: str):
    if state != request.session.pop("oauth_state", None):
        return RedirectResponse("/auth/login")

    redirect_uri = str(request.url_for("callback"))
    token_result = exchange_code_for_token(code=code, redirect_uri=redirect_uri)

    request.session["user"] = {
        "oid": token_result["id_token_claims"]["oid"],
        "name": token_result["id_token_claims"].get("name", ""),
        "roles": token_result["id_token_claims"].get("roles", []),
    }
    return RedirectResponse("/")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
