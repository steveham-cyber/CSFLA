"""
Role bypass security tests.

These tests attempt common role escalation and access control bypass
techniques against the API layer. They complement the auth tests in
test_api/test_auth.py with adversarial patterns.

See Test Strategy v0.1 Section 4.8.
"""

import pytest


class TestHTTPMethodBypass:
    """Changing HTTP method must not bypass role checks."""

    async def test_options_import_endpoint_no_403_leak(self, anon_client) -> None:
        """OPTIONS preflight must not expose protected data."""
        response = await anon_client.options("/api/imports/")
        # OPTIONS may return 200 (CORS preflight) or 405 — but not 200 with data
        assert response.status_code in (200, 204, 405)
        # Body must not contain any import batch data
        if response.status_code == 200:
            body = response.text
            assert "batch_id" not in body
            assert "pseudo_id" not in body


class TestURLManipulationBypass:
    """URL parameter manipulation must not bypass authentication."""

    async def test_trailing_slash_does_not_bypass_auth(self, anon_client) -> None:
        # FastAPI may redirect trailing-slash to canonical URL (307) before
        # auth runs — that redirect does not expose data, so 307 is acceptable.
        response = await anon_client.get("/api/admin/audit-log/")
        assert response.status_code in (307, 401, 404)

    async def test_case_variation_does_not_bypass_auth(self, anon_client) -> None:
        response = await anon_client.get("/API/admin/audit-log")
        assert response.status_code in (401, 404)

    async def test_path_traversal_does_not_bypass_auth(self, anon_client) -> None:
        response = await anon_client.get("/api/reports/../admin/audit-log")
        assert response.status_code in (401, 404)


class TestHeaderManipulationBypass:
    """Injected headers must not escalate privileges."""

    async def test_x_forwarded_user_header_ignored(self, anon_client) -> None:
        """A spoofed X-Forwarded-User header must not bypass authentication."""
        response = await anon_client.get(
            "/api/admin/audit-log",
            headers={"X-Forwarded-User": "admin"},
        )
        assert response.status_code == 401

    async def test_x_roles_header_ignored(self, anon_client) -> None:
        """A spoofed X-Roles header must not grant admin access."""
        response = await anon_client.get(
            "/api/admin/audit-log",
            headers={"X-Roles": "admin"},
        )
        assert response.status_code == 401

    async def test_authorization_bearer_random_token_rejected(
        self, anon_client
    ) -> None:
        """A random Bearer token (not a valid session) must be rejected."""
        response = await anon_client.get(
            "/api/admin/audit-log",
            headers={"Authorization": "Bearer random.token.value"},
        )
        # Should be 401 (no valid session) — not 200 or 403 (which would mean it
        # partially processed the token)
        assert response.status_code == 401


class TestPrivilegeEscalation:
    """A lower-privilege role must not be able to access higher-privilege endpoints."""

    async def test_viewer_cannot_escalate_to_admin(
        self, viewer_client
    ) -> None:
        """Viewer with admin-sounding path variation still gets 403."""
        response = await viewer_client.get("/api/admin/users")
        assert response.status_code == 403

    async def test_researcher_cannot_escalate_to_admin(
        self, researcher_client
    ) -> None:
        response = await researcher_client.get("/api/admin/users")
        assert response.status_code == 403

    async def test_viewer_cannot_escalate_via_import(
        self, viewer_client
    ) -> None:
        import io
        response = await viewer_client.post(
            "/api/imports/",
            files={"file": ("esc.csv", io.BytesIO(b"id\n1"), "text/csv")},
        )
        assert response.status_code == 403
