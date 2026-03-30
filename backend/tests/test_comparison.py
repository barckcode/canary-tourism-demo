"""Tests for inter-island province comparison endpoint.

Covers:
- New Las Palmas series IDs are present in INE_SERIES
- Comparison endpoint returns correct structure
- Indicator filter works
- Period limit works
- Invalid indicator returns 400
- Both provinces appear in response
"""

import pytest

from app.api.comparison import PROVINCE_INDICATORS, VALID_INDICATORS
from app.etl.sources import ine


# ---------------------------------------------------------------------------
# INE_SERIES configuration tests
# ---------------------------------------------------------------------------

class TestLasPalmasSeriesConfig:
    """Verify that Las Palmas hotel series are properly configured."""

    def _series_ids(self):
        return [s[0] for s in ine.INE_SERIES]

    def _series_indicators(self):
        return [s[1] for s in ine.INE_SERIES]

    def _series_geo_codes(self):
        return {s[0]: s[2] for s in ine.INE_SERIES}

    def test_viajeros_las_palmas_present(self):
        """EOT1547 hotel_viajeros_las_palmas should be in INE_SERIES."""
        assert "EOT1547" in self._series_ids()

    def test_pernoctaciones_las_palmas_present(self):
        """EOT1550 hotel_pernoctaciones_las_palmas should be in INE_SERIES."""
        assert "EOT1550" in self._series_ids()

    def test_estancia_media_las_palmas_present(self):
        """EOT7808 hotel_estancia_media_las_palmas should be in INE_SERIES."""
        assert "EOT7808" in self._series_ids()

    def test_ocupacion_plazas_las_palmas_present(self):
        """EOT159 hotel_ocupacion_plazas_las_palmas should be in INE_SERIES."""
        assert "EOT159" in self._series_ids()

    def test_las_palmas_indicator_names(self):
        """Las Palmas indicators should have correct names."""
        indicators = self._series_indicators()
        assert "hotel_viajeros_las_palmas" in indicators
        assert "hotel_pernoctaciones_las_palmas" in indicators
        assert "hotel_estancia_media_las_palmas" in indicators
        assert "hotel_ocupacion_plazas_las_palmas" in indicators

    def test_las_palmas_geo_code(self):
        """Las Palmas series should use ES701 geo_code."""
        geo_map = self._series_geo_codes()
        las_palmas_ids = {"EOT1547", "EOT1550", "EOT7808", "EOT159"}
        for sid in las_palmas_ids:
            assert geo_map[sid] == "ES701", (
                f"Series {sid} should use ES701 geo_code, got {geo_map[sid]}"
            )

    def test_total_series_count(self):
        """INE_SERIES should include the 4 new Las Palmas entries (41 total)."""
        assert len(ine.INE_SERIES) == 41


# ---------------------------------------------------------------------------
# GET /api/comparison/provinces - basic structure
# ---------------------------------------------------------------------------

class TestComparisonEndpoint:
    """Test the province comparison endpoint."""

    def test_default_returns_200(self, client):
        """GET /api/comparison/provinces should return 200 with default params."""
        resp = client.get("/api/comparison/provinces")
        assert resp.status_code == 200

    def test_default_indicator_is_pernoctaciones(self, client):
        """Default indicator should be 'pernoctaciones'."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        assert data["indicator"] == "pernoctaciones"

    def test_response_has_both_provinces(self, client):
        """Response should contain data for both ES709 and ES701."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]

    def test_province_names(self, client):
        """Province entries should have correct names."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        assert data["provinces"]["ES709"]["name"] == "Santa Cruz de Tenerife"
        assert data["provinces"]["ES701"]["name"] == "Las Palmas"

    def test_province_data_has_period_and_value(self, client):
        """Each data point should have period and value fields."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            province = data["provinces"][geo_code]
            assert len(province["data"]) > 0
            point = province["data"][0]
            assert "period" in point
            assert "value" in point

    def test_data_sorted_chronologically(self, client):
        """Data points should be in ascending chronological order."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            periods = [p["period"] for p in data["provinces"][geo_code]["data"]]
            assert periods == sorted(periods)


# ---------------------------------------------------------------------------
# Indicator filter
# ---------------------------------------------------------------------------

class TestComparisonIndicatorFilter:
    """Test that indicator query parameter works correctly."""

    @pytest.mark.parametrize("indicator", VALID_INDICATORS)
    def test_valid_indicator(self, client, indicator):
        """Each valid indicator should return 200."""
        resp = client.get(f"/api/comparison/provinces?indicator={indicator}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == indicator

    def test_invalid_indicator_returns_400(self, client):
        """An invalid indicator should return HTTP 400."""
        resp = client.get("/api/comparison/provinces?indicator=invalid_metric")
        assert resp.status_code == 400
        assert "Invalid indicator" in resp.json()["detail"]

    def test_viajeros_indicator(self, client):
        """Requesting 'viajeros' should return viajeros data for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=viajeros")
        data = resp.json()
        assert data["indicator"] == "viajeros"
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]


# ---------------------------------------------------------------------------
# Period limit
# ---------------------------------------------------------------------------

class TestComparisonPeriodLimit:
    """Test that the periods query parameter limits results."""

    def test_periods_limits_data(self, client):
        """Setting periods=6 should return at most 6 data points per province."""
        resp = client.get("/api/comparison/provinces?periods=6")
        assert resp.status_code == 200
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) <= 6

    def test_periods_default_24(self, client):
        """Default periods should return up to 24 data points."""
        resp = client.get("/api/comparison/provinces")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) <= 24

    def test_periods_1(self, client):
        """Setting periods=1 should return exactly 1 data point."""
        resp = client.get("/api/comparison/provinces?periods=1")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) == 1

    def test_large_periods_returns_all_available(self, client):
        """Setting a large periods value should return all available data."""
        resp = client.get("/api/comparison/provinces?periods=120")
        assert resp.status_code == 200
        data = resp.json()
        # Test data has 4 years * 12 months = 48 points
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) == 48
