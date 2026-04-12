"""
Entra ID (Azure AD) authentication via OIDC / MSAL.

Flow:
  1. User hits /auth/login → redirected to Entra ID sign-in
  2. Entra ID redirects to /auth/callback with an auth code
  3. App exchanges code for tokens via MSAL
  4. ID token validated; user role resolved from Entra ID group membership
  5. Session established

Role mapping:
  Roles are assigned via Entra ID App Role assignments — not stored in the application DB.
  Roles: admin | researcher | viewer
"""

import msal
from fastapi import HTTPException, Request, status
from functools import lru_cache

from config import get_settings

settings = get_settings()

AUTHORITY = f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
SCOPES = []  # MSAL adds openid/profile/offline_access automatically


@lru_cache
def get_msal_app() -> msal.ConfidentialClientApplication:
    """
    Returns a cached MSAL confidential client.
    In Azure, the client secret is empty and Managed Identity is used.
    For local dev, azure_client_secret is set in .env.
    """
    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret or None,
        authority=AUTHORITY,
    )


def get_auth_url(redirect_uri: str, state: str) -> str:
    return get_msal_app().get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )


def exchange_code_for_token(code: str, redirect_uri: str) -> dict:
    result = get_msal_app().acquire_token_by_authorization_code(
        code=code,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {result.get('error_description', result['error'])}",
        )
    return result


def get_user_roles(token_claims: dict) -> list[str]:
    """
    Extract app roles from the token claims.
    Roles are assigned in Entra ID App Registration → App roles.
    """
    return token_claims.get("roles", [])


class CurrentUser:
    def __init__(self, claims: dict):
        self.id: str = claims["oid"]          # Entra ID object ID — used as audit log identifier
        self.name: str = claims.get("name", "")
        self.roles: list[str] = get_user_roles(claims)

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)

    def require_role(self, *roles: str) -> None:
        if not self.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
