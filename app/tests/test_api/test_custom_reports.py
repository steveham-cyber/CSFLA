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


class TestBlockRegistry:
    """Verify block registry completeness and run_block dispatch."""

    def test_all_eight_blocks_registered(self) -> None:
        from reports.blocks import BLOCKS
        assert set(BLOCKS.keys()) == {"r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"}

    def test_each_block_has_required_keys(self) -> None:
        from reports.blocks import BLOCKS
        for block_id, block in BLOCKS.items():
            assert "title" in block, f"{block_id} missing title"
            assert "description" in block, f"{block_id} missing description"
            assert "filters" in block, f"{block_id} missing filters"
            assert "run" in block, f"{block_id} missing run"
            assert callable(block["run"]), f"{block_id} run must be callable"

    def test_run_block_rejects_unknown_block(self) -> None:
        import asyncio
        from reports.blocks import run_block

        async def _run():
            with pytest.raises(ValueError, match="Unknown block"):
                await run_block(None, "r99", {})

        asyncio.get_event_loop().run_until_complete(_run())

    def test_run_block_strips_unknown_filter_keys(self, db_session) -> None:
        """run_block must silently ignore filters not accepted by the block."""
        import asyncio
        from reports.blocks import run_block

        async def _run():
            # r1 (Cohort Overview) accepts NO filters — unknown keys must be stripped
            result = await run_block(db_session, "r1", {"country": "GB", "gender": "female"})
            assert isinstance(result, dict)

        asyncio.get_event_loop().run_until_complete(_run())
