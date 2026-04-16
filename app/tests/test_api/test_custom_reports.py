"""
Custom report tests — query builder unit tests + API tests.
DB-dependent tests require the test PostgreSQL instance (csfleak_test).
Tests without a db_session fixture run without a DB connection.
"""
import pytest


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
