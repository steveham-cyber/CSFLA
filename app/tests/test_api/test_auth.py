"""
API authentication and role enforcement tests.

These tests verify that:
  - Unauthenticated requests are rejected with 401
  - Role-based access control is enforced at the API layer
  - Role checks are in the FastAPI dependency, not the frontend

All role-enforcement tests are BLOCKING. See Test Strategy v0.1 Section 4.8.

Note: These tests use the viewer_client, researcher_client, and admin_client
fixtures from conftest.py, which override get_current_user via
app.dependency_overrides. This tests the dependency chain, not Entra ID itself.
"""

import pytest


# ── Unauthenticated request tests ─────────────────────────────────────────────

class TestUnauthenticated:
    """Requests without a valid session must receive HTTP 401."""

    async def test_import_endpoint_rejects_unauthenticated(self, anon_client) -> None:
        import io
        response = await anon_client.post(
            "/api/imports/",
            files={"file": ("test.csv", io.BytesIO(b"id,country\n1,England"), "text/csv")},
        )
        assert response.status_code == 401

    async def test_reports_endpoint_rejects_unauthenticated(self, anon_client) -> None:
        response = await anon_client.get("/api/reports/")
        assert response.status_code == 401

    async def test_report_detail_rejects_unauthenticated(self, anon_client) -> None:
        response = await anon_client.get("/api/reports/cohort")
        assert response.status_code == 401

    async def test_admin_users_rejects_unauthenticated(self, anon_client) -> None:
        response = await anon_client.get("/api/admin/users")
        assert response.status_code == 401

    async def test_admin_audit_log_rejects_unauthenticated(self, anon_client) -> None:
        response = await anon_client.get("/api/admin/audit-log")
        assert response.status_code == 401

    async def test_health_endpoint_accessible_without_auth(self, anon_client) -> None:
        """Health check must be publicly accessible for Azure health probes."""
        response = await anon_client.get("/health")
        assert response.status_code == 200


# ── Viewer role tests ─────────────────────────────────────────────────────────

class TestViewerRole:
    """Viewer role can access reports but must not trigger imports or admin actions."""

    async def test_viewer_can_access_reports_list(self, viewer_client) -> None:
        response = await viewer_client.get("/api/reports/")
        assert response.status_code == 200

    async def test_viewer_can_access_report_detail(self, viewer_client) -> None:
        response = await viewer_client.get("/api/reports/cohort")
        assert response.status_code == 200

    async def test_viewer_cannot_trigger_import(self, viewer_client) -> None:
        """POST /api/imports/ must return 403 for viewer role."""
        import io
        response = await viewer_client.post(
            "/api/imports/",
            files={"file": ("test.csv", io.BytesIO(b"id,country\n1001,England"), "text/csv")},
        )
        assert response.status_code == 403

    async def test_viewer_cannot_access_admin_users(self, viewer_client) -> None:
        response = await viewer_client.get("/api/admin/users")
        assert response.status_code == 403

    async def test_viewer_cannot_access_audit_log(self, viewer_client) -> None:
        response = await viewer_client.get("/api/admin/audit-log")
        assert response.status_code == 403


# ── Researcher role tests ─────────────────────────────────────────────────────

class TestResearcherRole:
    """Researcher role can access reports but must not trigger imports or admin actions."""

    async def test_researcher_can_access_reports_list(self, researcher_client) -> None:
        response = await researcher_client.get("/api/reports/")
        assert response.status_code == 200

    async def test_researcher_can_access_report_detail(self, researcher_client) -> None:
        response = await researcher_client.get("/api/reports/cohort")
        assert response.status_code == 200

    async def test_researcher_cannot_trigger_import(self, researcher_client) -> None:
        """
        POST /api/imports/ must return 403 for researcher role.
        This is the direct-HTTP-bypass test: the role check is in the
        FastAPI dependency, not the frontend.
        """
        import io
        response = await researcher_client.post(
            "/api/imports/",
            files={"file": ("test.csv", io.BytesIO(b"id,country\n1001,England"), "text/csv")},
        )
        assert response.status_code == 403

    async def test_researcher_cannot_access_admin_audit_log(self, researcher_client) -> None:
        response = await researcher_client.get("/api/admin/audit-log")
        assert response.status_code == 403

    async def test_researcher_cannot_access_admin_users(self, researcher_client) -> None:
        response = await researcher_client.get("/api/admin/users")
        assert response.status_code == 403


# ── Admin role tests ──────────────────────────────────────────────────────────

class TestAdminRole:
    """Admin role must be able to access all endpoints without 401 or 403."""

    async def test_admin_can_access_reports(self, admin_client) -> None:
        response = await admin_client.get("/api/reports/")
        assert response.status_code not in (401, 403)

    async def test_admin_can_access_admin_users(self, admin_client) -> None:
        response = await admin_client.get("/api/admin/users")
        assert response.status_code not in (401, 403)

    async def test_admin_can_access_audit_log(self, admin_client) -> None:
        response = await admin_client.get("/api/admin/audit-log")
        assert response.status_code not in (401, 403)

    async def test_admin_can_access_import_batches(self, admin_client) -> None:
        response = await admin_client.get("/api/admin/batches")
        assert response.status_code not in (401, 403)

    async def test_admin_upload_import_returns_501_not_403(self, admin_client) -> None:
        """
        Admin can call POST /api/imports/ but the pipeline is locked (501).
        This verifies the role check passes for admin; 501 is the expected
        response until Cipher + Lex sign off on the pipeline (ACTIONS.md A-07, A-10).
        """
        import io
        response = await admin_client.post(
            "/api/imports/",
            files={"file": ("test.csv", io.BytesIO(b"id,country\n1001,England"), "text/csv")},
        )
        assert response.status_code == 501, (
            f"Expected 501 (pipeline locked), got {response.status_code}. "
            "If this is 403, the admin role check is failing. "
            "If this is 200, the pipeline was unexpectedly unlocked."
        )


# ── Role check at API layer, not UI ──────────────────────────────────────────

class TestRoleCheckAtAPILayer:
    """
    Verify that role enforcement is in the FastAPI dependency, not the frontend.
    Direct HTTP calls that bypass the UI must receive the same 403 responses.
    """

    async def test_direct_http_import_call_with_viewer_gets_403(
        self, viewer_client
    ) -> None:
        """
        Simulates a user who bypasses the UI and calls the import endpoint directly.
        The API layer must enforce the role check regardless.
        """
        import io
        response = await viewer_client.post(
            "/api/imports/",
            files={"file": ("bypass.csv", io.BytesIO(b"id\n1"), "text/csv")},
        )
        assert response.status_code == 403

    async def test_direct_http_admin_call_with_researcher_gets_403(
        self, researcher_client
    ) -> None:
        """Researcher calling admin endpoint directly must receive 403."""
        response = await researcher_client.get("/api/admin/audit-log")
        assert response.status_code == 403
