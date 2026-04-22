import secrets
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from auth.entra import get_auth_url, exchange_code_for_token
from config import get_settings

router = APIRouter()
settings = get_settings()


def _callback_uri(request: Request) -> str:
    """
    Build the OAuth callback URI.
    Azure App Service terminates TLS at the load balancer, so request.url_for()
    returns http:// even when the user is on https://. Force https:// in
    non-local environments so the URI matches the Entra ID App Registration.
    """
    uri = str(request.url_for("callback"))
    if not settings.is_local:
        uri = uri.replace("http://", "https://", 1)
    return uri


@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    redirect_uri = _callback_uri(request)
    return RedirectResponse(get_auth_url(redirect_uri=redirect_uri, state=state))


@router.get("/callback")
async def callback(request: Request, code: str, state: str):
    if state != request.session.pop("oauth_state", None):
        return RedirectResponse("/auth/login")

    redirect_uri = _callback_uri(request)
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
