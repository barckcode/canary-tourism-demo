"""Tests for EPA employment indicators integration.

Covers:
- New EPA series IDs are present in INE_SERIES
- Dashboard KPIs endpoint returns employment fields
- YoY calculation logic works correctly when data exists
- Quarterly period parsing for EPA data
"""

import pytest

from app.etl.sources import ine


# ---------------------------------------------------------------------------
# INE_SERIES configuration tests
# ---------------------------------------------------------------------------

class TestEPASeriesConfig:
    """Verify that EPA employment series are properly configured."""

    def _series_ids(self):
        return [s[0] for s in ine.INE_SERIES]

    def _series_indicators(self):
        return [s[1] for s in ine.INE_SERIES]

    def test_epa_total_series_present(self):
        """EPA total occupied persons series should be in INE_SERIES."""
        assert "EPA440086" in self._series_ids()

    def test_epa_services_series_present(self):
        """EPA services sector occupied persons series should be in INE_SERIES."""
        assert "EPA440090" in self._series_ids()

    def test_epa_total_indicator_name(self):
        """EPA total indicator should have the correct name."""
        assert "epa_ocupados_total_canarias" in self._series_indicators()

    def test_epa_services_indicator_name(self):
        """EPA services indicator should have the correct name."""
        assert "epa_ocupados_servicios_canarias" in self._series_indicators()

    def test_epa_geo_code(self):
        """EPA series should use ES70 (Canarias CCAA level)."""
        epa_ids = {"EPA440086", "EPA440090"}
        for series_id, indicator, geo_code in ine.INE_SERIES:
            if series_id in epa_ids:
                assert geo_code == "ES70", (
                    f"Series {series_id} should use ES70 geo_code, got {geo_code}"
                )

    def test_epa_series_count(self):
        """INE_SERIES should include the 2 new EPA entries (41 total)."""
        assert len(ine.INE_SERIES) == 41


# ---------------------------------------------------------------------------
# Quarterly period parsing tests
# ---------------------------------------------------------------------------

class TestEPAQuarterlyParsing:
    """Test that quarterly EPA data is parsed correctly."""

    def test_parse_quarterly_q1(self):
        """Should parse FK_Periodo 19 as Q1."""
        data = [{"Anyo": 2025, "FK_Periodo": 19, "Valor": 1043.6}]
        records = ine._parse_series_records(
            data, "epa_ocupados_total_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["period"] == "2025-Q1"
        assert records[0]["value"] == 1043.6
        assert records[0]["source"] == "ine"
        assert records[0]["indicator"] == "epa_ocupados_total_canarias"
        assert records[0]["geo_code"] == "ES70"

    def test_parse_quarterly_q2(self):
        """Should parse FK_Periodo 20 as Q2."""
        data = [{"Anyo": 2025, "FK_Periodo": 20, "Valor": 1050.2}]
        records = ine._parse_series_records(
            data, "epa_ocupados_servicios_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["period"] == "2025-Q2"

    def test_parse_quarterly_q3(self):
        """Should parse FK_Periodo 21 as Q3."""
        data = [{"Anyo": 2025, "FK_Periodo": 21, "Valor": 1060.0}]
        records = ine._parse_series_records(
            data, "epa_ocupados_total_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["period"] == "2025-Q3"

    def test_parse_quarterly_q4(self):
        """Should parse FK_Periodo 22 as Q4."""
        data = [{"Anyo": 2025, "FK_Periodo": 22, "Valor": 1055.0}]
        records = ine._parse_series_records(
            data, "epa_ocupados_total_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["period"] == "2025-Q4"

    def test_parse_skips_null_values(self):
        """Should skip records with None Valor."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 19, "Valor": None},
            {"Anyo": 2025, "FK_Periodo": 20, "Valor": 900.5},
        ]
        records = ine._parse_series_records(
            data, "epa_ocupados_total_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["value"] == 900.5

    def test_parse_multiple_quarters(self):
        """Should parse a full year of quarterly data."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 19, "Valor": 1040.0},
            {"Anyo": 2025, "FK_Periodo": 20, "Valor": 1050.0},
            {"Anyo": 2025, "FK_Periodo": 21, "Valor": 1060.0},
            {"Anyo": 2025, "FK_Periodo": 22, "Valor": 1055.0},
        ]
        records = ine._parse_series_records(
            data, "epa_ocupados_total_canarias", "ES70"
        )
        assert len(records) == 4
        periods = [r["period"] for r in records]
        assert periods == ["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"]


# ---------------------------------------------------------------------------
# Dashboard KPI endpoint tests
# ---------------------------------------------------------------------------

class TestDashboardEmploymentKPIs:
    """Test that the dashboard KPIs endpoint returns employment data."""

    def test_kpis_include_employment_total(self, client):
        """Dashboard KPIs should include employment_total from EPA."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "employment_total" in data
        if data["data_available"]:
            assert data["employment_total"] is not None
            assert data["employment_total"] > 0

    def test_kpis_include_employment_services(self, client):
        """Dashboard KPIs should include employment_services from EPA."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "employment_services" in data
        if data["data_available"]:
            assert data["employment_services"] is not None
            assert data["employment_services"] > 0

    def test_kpis_include_employment_yoy_fields(self, client):
        """Dashboard KPIs should include YoY change fields for employment."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "employment_total_yoy" in data
        assert "employment_services_yoy" in data

    def test_kpis_employment_yoy_values(self, client):
        """Employment YoY values should be present when data exists."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data["data_available"] and data.get("employment_total") is not None:
            # With test seed data spanning 2022-2025, YoY should be calculable
            assert data["employment_total_yoy"] is not None
            assert data["employment_services_yoy"] is not None

    def test_kpis_employment_values_reasonable(self, client):
        """Employment KPI values should be within expected ranges (thousands)."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data.get("employment_total") is not None:
            # Total occupied in Canarias: typically 700-1200 thousand
            assert 500 <= data["employment_total"] <= 2000, (
                f"employment_total {data['employment_total']} outside expected range"
            )
        if data.get("employment_services") is not None:
            # Services sector: typically 600-1000 thousand
            assert 400 <= data["employment_services"] <= 1500, (
                f"employment_services {data['employment_services']} outside expected range"
            )

    def test_kpis_services_less_than_total(self, client):
        """Services employment should be less than or equal to total employment."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if (
            data.get("employment_total") is not None
            and data.get("employment_services") is not None
        ):
            assert data["employment_services"] <= data["employment_total"], (
                "Services employment should not exceed total employment"
            )

    def test_kpis_no_data_includes_employment_fields(self, client, db):
        """Even with no arrivals data, employment fields should be in response schema."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        # The response should always contain these fields (may be None)
        for field in [
            "employment_total",
            "employment_total_yoy",
            "employment_services",
            "employment_services_yoy",
        ]:
            assert field in data, f"Field '{field}' missing from KPIs response"
