"""
Custom report tests — query builder unit tests + API tests.
DB-dependent tests require the test PostgreSQL instance (csfleak_test).
Tests without a db_session fixture run without a DB connection.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CustomReportAudit


class TestQueryBuilderUnit:
    """Pure unit tests — no DB needed."""

    def test_valid_field_keys(self) -> None:
        from reports.query_builder import VALID_FIELD_KEYS
        assert VALID_FIELD_KEYS == {
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        }

    def test_field_order(self) -> None:
        from reports.query_builder import FIELD_ORDER
        assert FIELD_ORDER == [
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        ]

    def test_cause_group_col_expr_uses_col_alias(self) -> None:
        from reports.query_builder import _CAUSE_GROUP_COL_EXPR
        assert "col.cause" in _CAUSE_GROUP_COL_EXPR
        assert "CASE" in _CAUSE_GROUP_COL_EXPR

    def test_cause_group_col_expr_covers_all_groups(self) -> None:
        from reports.query_builder import _CAUSE_GROUP_COL_EXPR
        for group in ("Iatrogenic", "Connective Tissue Disorder",
                      "Spontaneous / Structural", "Traumatic"):
            assert group in _CAUSE_GROUP_COL_EXPR

    def test_available_fields_has_six_entries(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        assert len(AVAILABLE_FIELDS) == 6

    def test_leak_type_has_four_enum_values(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        assert set(AVAILABLE_FIELDS["leak_type"]["values"]) == {
            "spinal", "cranial", "spinalAndCranial", "unknown",
        }

    def test_dynamic_fields_have_no_values_list(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        for key in ("country", "gender", "age_band"):
            assert AVAILABLE_FIELDS[key]["dynamic"] is True
            assert "values" not in AVAILABLE_FIELDS[key]

    def test_enum_fields_have_values_list(self) -> None:
        from reports.query_builder import AVAILABLE_FIELDS
        for key in ("leak_type", "cause_group", "individual_cause"):
            assert AVAILABLE_FIELDS[key]["dynamic"] is False
            assert isinstance(AVAILABLE_FIELDS[key]["values"], list)
            assert len(AVAILABLE_FIELDS[key]["values"]) > 0


class TestCustomReportAuth:
    """Auth enforcement — no DB needed."""

    async def test_fields_requires_auth(self, anon_client) -> None:
        response = await anon_client.get("/api/custom-reports/fields")
        assert response.status_code == 401

    async def test_list_requires_auth(self, anon_client) -> None:
        response = await anon_client.get("/api/custom-reports/")
        assert response.status_code == 401

    async def test_run_requires_auth(self, anon_client) -> None:
        response = await anon_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 401

    async def test_create_requires_auth(self, anon_client) -> None:
        response = await anon_client.post(
            "/api/custom-reports/",
            json={"name": "x", "definition": {"dimensions": ["country"]}},
        )
        assert response.status_code == 401


class TestViewerRoleExclusion:
    """Viewer role must be excluded from all custom report builder endpoints."""

    async def test_viewer_cannot_list_reports(self, viewer_client_no_db) -> None:
        response = await viewer_client_no_db.get("/api/custom-reports/")
        assert response.status_code == 403

    async def test_viewer_cannot_run_adhoc(self, viewer_client_no_db) -> None:
        response = await viewer_client_no_db.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 403

    async def test_viewer_cannot_create_report(self, viewer_client_no_db) -> None:
        response = await viewer_client_no_db.post(
            "/api/custom-reports/",
            json={"name": "Viewer Report", "definition": {"dimensions": ["country"]}},
        )
        assert response.status_code == 403

    async def test_viewer_cannot_access_fields(self, viewer_client_no_db) -> None:
        response = await viewer_client_no_db.get("/api/custom-reports/fields")
        assert response.status_code == 403


class TestQueryDefinitionValidation:
    """Pydantic validation — no DB needed (422 returned before DB is touched)."""

    async def test_run_empty_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run", json={"dimensions": []}
        )
        assert response.status_code == 422

    async def test_run_unknown_dimension_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run", json={"dimensions": ["nonexistent_field"]}
        )
        assert response.status_code == 422

    async def test_run_duplicate_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country", "country"]},
        )
        assert response.status_code == 422

    async def test_run_seven_dimensions_returns_422(
        self, researcher_client
    ) -> None:
        # Only 6 fields exist; any list longer than 6 is invalid
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": [
                    "country", "gender", "age_band",
                    "leak_type", "cause_group", "individual_cause",
                    "country",   # 7th = duplicate triggers duplicate error
                ]
            },
        )
        assert response.status_code == 422

    async def test_run_unknown_filter_field_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"], "filters": {"bogus": ["val"]}},
        )
        assert response.status_code == 422

    async def test_run_empty_filter_values_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"], "filters": {"gender": []}},
        )
        assert response.status_code == 422

    async def test_create_empty_name_returns_422(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "", "definition": {"dimensions": ["country"]}},
        )
        assert response.status_code == 422


class TestUIRoutes:
    """Builder pages require auth — no DB needed.

    UI routes use Starlette session cookies for auth (not the API Bearer token
    dependency), so authenticated access can only be verified in a browser/
    integration test where a real session is established. We test only the
    unauthenticated redirect path here, which is fully exercised via httpx.
    """

    async def test_builder_redirects_unauthenticated(
        self, anon_client
    ) -> None:
        response = await anon_client.get("/reports/builder")
        # UI routes redirect (302) rather than returning 401
        assert response.status_code == 302

    async def test_builder_new_redirects_unauthenticated(
        self, anon_client
    ) -> None:
        response = await anon_client.get("/reports/builder/new")
        assert response.status_code == 302


class TestFieldsEndpoint:
    """DB-dependent: queries distinct values for dynamic fields."""

    async def test_fields_returns_six_fields(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        assert response.status_code == 200
        data = response.json()
        assert len(data["fields"]) == 6

    async def test_field_keys_in_correct_order(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        keys = [f["key"] for f in response.json()["fields"]]
        assert keys == [
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        ]

    async def test_each_field_has_key_label_values(
        self, researcher_client
    ) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        for field in response.json()["fields"]:
            assert "key" in field
            assert "label" in field
            assert isinstance(field["values"], list)

    async def test_leak_type_enum_values(self, researcher_client) -> None:
        response = await researcher_client.get("/api/custom-reports/fields")
        lt = next(
            f for f in response.json()["fields"] if f["key"] == "leak_type"
        )
        assert set(lt["values"]) == {
            "spinal", "cranial", "spinalAndCranial", "unknown"
        }


class TestRunEndpoint:
    """DB-dependent: exercises the query builder end-to-end."""

    async def test_run_returns_correct_shape(
        self, researcher_client
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == ["country"]
        assert "rows" in data
        assert "total_shown" in data
        assert "suppressed_count" in data
        assert isinstance(data["suppressed_count"], int)

    async def test_run_result_rows_respect_k10(
        self, researcher_client
    ) -> None:
        """All returned rows must have member_count >= 10."""
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        for row in response.json()["rows"]:
            assert row["member_count"] >= 10

    async def test_run_with_filter_narrows_results(
        self, researcher_client
    ) -> None:
        """Running with a country filter must only return rows for that country."""
        full = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country", "gender"]},
        )
        rows = full.json()["rows"]
        if not rows:
            pytest.skip("No data in test DB — cannot verify filter behaviour")
        first_country = rows[0]["country"]
        filtered = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": ["country", "gender"],
                "filters": {"country": [first_country]},
            },
        )
        for row in filtered.json()["rows"]:
            assert row["country"] == first_country

    # DEFECT-04: All 6 dimensions
    async def test_run_all_six_dimensions(self, researcher_client) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country", "gender", "age_band",
                                 "leak_type", "cause_group", "individual_cause"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["columns"] == [
            "country", "gender", "age_band",
            "leak_type", "cause_group", "individual_cause",
        ]

    # DEFECT-05: Filter on non-dimension field
    async def test_run_filter_on_non_dimension_field(
        self, researcher_client
    ) -> None:
        # country is the dimension; gender is filter-only (not in dimensions)
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": ["country"],
                "filters": {"gender": ["female"]},
            },
        )
        assert response.status_code == 200
        # columns should only contain the dimension, not the filter field
        assert response.json()["columns"] == ["country"]

    # DEFECT-06: cause_group filter path
    async def test_run_cause_group_filter(self, researcher_client) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={
                "dimensions": ["country"],
                "filters": {"cause_group": ["Iatrogenic"]},
            },
        )
        assert response.status_code == 200
        # cause_group uses a CASE WHEN expression in WHERE — verify it doesn't error
        assert "rows" in response.json()

    # DEFECT-02: Audit row assertions
    async def test_run_adhoc_writes_audit_row(
        self, researcher_client, db_session
    ) -> None:
        await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        result = await db_session.execute(
            select(CustomReportAudit).where(
                CustomReportAudit.action == "run_adhoc"
            )
        )
        rows = result.scalars().all()
        assert len(rows) >= 1
        row = rows[-1]
        assert row.action == "run_adhoc"
        assert row.report_id is None
        assert row.performed_by == "00000000-0000-0000-0000-researcher00"

    async def test_run_saved_writes_audit_row(
        self, researcher_client, db_session
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Audit Test Report", "definition": {"dimensions": ["country"]}},
        )
        assert create.status_code == 201
        report_id = create.json()["id"]

        await researcher_client.post(f"/api/custom-reports/{report_id}/run")

        result = await db_session.execute(
            select(CustomReportAudit).where(
                CustomReportAudit.action == "run",
                CustomReportAudit.report_id == uuid.UUID(report_id),
            )
        )
        rows = result.scalars().all()
        assert len(rows) >= 1
        assert str(rows[-1].report_id) == report_id


class TestCustomReportCRUD:
    """DB-dependent: full CRUD lifecycle."""

    _defn = {"dimensions": ["country", "gender"]}

    async def test_create_returns_201(self, researcher_client) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Test Report", "definition": self._defn},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Report"
        assert "id" in data
        assert data["definition"]["dimensions"] == ["country", "gender"]

    async def test_list_returns_own_reports_only(
        self, researcher_client, admin_client
    ) -> None:
        await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Researcher Report", "definition": self._defn},
        )
        admin_list = await admin_client.get("/api/custom-reports/")
        names = [r["name"] for r in admin_list.json()["reports"]]
        assert "Researcher Report" not in names

    async def test_get_own_report_returns_200(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "My Report", "definition": self._defn},
        )
        report_id = create.json()["id"]
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 200
        assert get.json()["name"] == "My Report"

    async def test_get_other_users_report_returns_404(
        self, researcher_client, admin_client
    ) -> None:
        create = await admin_client.post(
            "/api/custom-reports/",
            json={"name": "Admin Report", "definition": self._defn},
        )
        report_id = create.json()["id"]
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 404

    async def test_delete_own_report_returns_204(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Delete Me", "definition": self._defn},
        )
        report_id = create.json()["id"]
        delete = await researcher_client.post(
            f"/api/custom-reports/{report_id}/delete"
        )
        assert delete.status_code == 204
        get = await researcher_client.get(f"/api/custom-reports/{report_id}")
        assert get.status_code == 404

    async def test_run_saved_report_returns_query_result(
        self, researcher_client
    ) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Run Me", "definition": self._defn},
        )
        report_id = create.json()["id"]
        run = await researcher_client.post(
            f"/api/custom-reports/{report_id}/run"
        )
        assert run.status_code == 200
        data = run.json()
        assert data["columns"] == ["country", "gender"]
        assert "suppressed_count" in data
        assert data["report_id"] == report_id

    async def test_run_includes_suppressed_count(
        self, researcher_client
    ) -> None:
        """High-cardinality definition maximises suppression probability."""
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={
                "name": "High Cardinality",
                "definition": {
                    "dimensions": [
                        "country", "gender", "age_band",
                        "leak_type", "cause_group",
                    ]
                },
            },
        )
        report_id = create.json()["id"]
        run = await researcher_client.post(
            f"/api/custom-reports/{report_id}/run"
        )
        assert run.status_code == 200
        assert isinstance(run.json()["suppressed_count"], int)

    # DEFECT-01: Update endpoint tests
    async def test_update_report_returns_200(self, researcher_client) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Original Name", "definition": {"dimensions": ["country"]}},
        )
        assert create.status_code == 201
        report_id = create.json()["id"]

        update = await researcher_client.post(
            f"/api/custom-reports/{report_id}",
            json={
                "name": "Updated Name",
                "definition": {"dimensions": ["gender"]},
            },
        )
        assert update.status_code == 200
        data = update.json()
        assert data["name"] == "Updated Name"
        assert data["definition"]["dimensions"] == ["gender"]

    async def test_update_preserves_id(self, researcher_client) -> None:
        create = await researcher_client.post(
            "/api/custom-reports/",
            json={"name": "Preserve ID Test", "definition": {"dimensions": ["country"]}},
        )
        assert create.status_code == 201
        original_id = create.json()["id"]

        update = await researcher_client.post(
            f"/api/custom-reports/{original_id}",
            json={"name": "New Name"},
        )
        assert update.status_code == 200
        assert update.json()["id"] == original_id

    async def test_update_other_users_report_returns_404(
        self, researcher_client, admin_client
    ) -> None:
        create = await admin_client.post(
            "/api/custom-reports/",
            json={"name": "Admin's Report", "definition": {"dimensions": ["country"]}},
        )
        assert create.status_code == 201
        report_id = create.json()["id"]

        update = await researcher_client.post(
            f"/api/custom-reports/{report_id}",
            json={"name": "Hijacked Name"},
        )
        assert update.status_code == 404

    # DEFECT-07: Invalid UUID in path param
    async def test_get_invalid_uuid_returns_404(
        self, researcher_client
    ) -> None:
        response = await researcher_client.get(
            "/api/custom-reports/not-a-valid-uuid"
        )
        assert response.status_code == 404


# DEFECT-03: k≥10 suppression test with real data
class TestRunEndpointWithData:
    """DB-dependent: seeds known counts to assert k≥10 suppression behaviour."""

    @pytest_asyncio.fixture
    async def cohort_with_small_group(self, db_session: AsyncSession):
        """
        Seeds two groups:
        - 12 members in England (above threshold — should appear)
        - 5 members in Scotland (below threshold — should be suppressed)
        """
        from tests.test_reports.conftest import _make_batch, _make_member

        batch = await _make_batch(db_session)
        await db_session.flush()
        bid = batch.batch_id

        for i in range(12):
            await _make_member(
                db_session, bid, f"eng-k10-{i:04d}",
                country="England",
            )

        for i in range(5):
            await _make_member(
                db_session, bid, f"sco-k10-{i:04d}",
                country="Scotland",
            )

        await db_session.flush()
        yield {"england": 12, "scotland": 5}

    async def test_k10_suppresses_small_cohorts(
        self, researcher_client, cohort_with_small_group
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 200
        data = response.json()
        countries = [r["country"] for r in data["rows"]]
        assert "England" in countries          # 12 members — shown
        assert "Scotland" not in countries     # 5 members — suppressed
        assert data["suppressed_count"] >= 1

    async def test_k10_shown_rows_all_meet_threshold(
        self, researcher_client, cohort_with_small_group
    ) -> None:
        response = await researcher_client.post(
            "/api/custom-reports/run",
            json={"dimensions": ["country"]},
        )
        assert response.status_code == 200
        for row in response.json()["rows"]:
            assert row["member_count"] >= 10
