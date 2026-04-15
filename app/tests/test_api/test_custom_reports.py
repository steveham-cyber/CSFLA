"""
Custom report API tests.
All tests use real DB sessions rolled back per test (see conftest.py).
"""
import pytest


class TestCustomReportModels:
    """Verify the DB tables exist and accept valid data."""

    async def test_custom_reports_table_exists(self, db_session) -> None:
        from sqlalchemy import text
        result = await db_session.execute(
            text("SELECT to_regclass('public.custom_reports')")
        )
        assert result.scalar() is not None, "custom_reports table must exist"

    async def test_custom_report_audit_table_exists(self, db_session) -> None:
        from sqlalchemy import text
        result = await db_session.execute(
            text("SELECT to_regclass('public.custom_report_audit')")
        )
        assert result.scalar() is not None, "custom_report_audit table must exist"
