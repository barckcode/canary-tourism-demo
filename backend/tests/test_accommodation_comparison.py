"""Tests for accommodation type comparison endpoint (rural vs hotel).

Covers:
- Endpoint returns correct structure
- All 3 indicators work (viajeros, pernoctaciones, plazas)
- Invalid indicator returns 400
- Period limiting works
- Both types (rural, hotel) appear in response
- Data is sorted chronologically
"""

import pytest

from app.api.comparison import ACCOMMODATION_INDICATORS, VALID_ACCOMMODATION_INDICATORS


# ---------------------------------------------------------------------------
# GET /api/comparison/accommodation-types - basic structure
# ---------------------------------------------------------------------------

class TestAccommodationComparisonEndpoint:
    """Test the accommodation type comparison endpoint."""

    def test_default_returns_200(self, client):
        """GET /api/comparison/accommodation-types should return 200."""
        resp = client.get("/api/comparison/accommodation-types")
        assert resp.status_code == 200

    def test_default_indicator_is_pernoctaciones(self, client):
        """Default indicator should be 'pernoctaciones'."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        assert data["indicator"] == "pernoctaciones"

    def test_response_has_both_types(self, client):
        """Response should contain data for both rural and hotel."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        assert "rural" in data["types"]
        assert "hotel" in data["types"]

    def test_type_names(self, client):
        """Type entries should have correct display names."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        assert data["types"]["rural"]["name"] == "Turismo Rural (Canarias)"
        assert data["types"]["hotel"]["name"] == "Hotel (SC Tenerife)"

    def test_data_has_period_and_value(self, client):
        """Each data point should have period and value fields."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        for accom_type in ["rural", "hotel"]:
            type_data = data["types"][accom_type]
            assert len(type_data["data"]) > 0
            point = type_data["data"][0]
            assert "period" in point
            assert "value" in point

    def test_data_sorted_chronologically(self, client):
        """Data points should be in ascending chronological order."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        for accom_type in ["rural", "hotel"]:
            periods = [p["period"] for p in data["types"][accom_type]["data"]]
            assert periods == sorted(periods)


# ---------------------------------------------------------------------------
# Indicator filter
# ---------------------------------------------------------------------------

class TestAccommodationIndicatorFilter:
    """Test that the indicator query parameter works correctly."""

    @pytest.mark.parametrize("indicator", VALID_ACCOMMODATION_INDICATORS)
    def test_valid_indicator(self, client, indicator):
        """Each valid indicator should return 200."""
        resp = client.get(
            f"/api/comparison/accommodation-types?indicator={indicator}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == indicator

    def test_invalid_indicator_returns_400(self, client):
        """An invalid indicator should return HTTP 400."""
        resp = client.get(
            "/api/comparison/accommodation-types?indicator=invalid_metric"
        )
        assert resp.status_code == 400
        assert "Invalid indicator" in resp.json()["detail"]

    def test_viajeros_indicator(self, client):
        """Requesting 'viajeros' should return data for both types."""
        resp = client.get(
            "/api/comparison/accommodation-types?indicator=viajeros"
        )
        data = resp.json()
        assert data["indicator"] == "viajeros"
        assert "rural" in data["types"]
        assert "hotel" in data["types"]

    def test_plazas_indicator(self, client):
        """Requesting 'plazas' should return data for both types."""
        resp = client.get(
            "/api/comparison/accommodation-types?indicator=plazas"
        )
        data = resp.json()
        assert data["indicator"] == "plazas"
        assert "rural" in data["types"]
        assert "hotel" in data["types"]


# ---------------------------------------------------------------------------
# Period limit
# ---------------------------------------------------------------------------

class TestAccommodationPeriodLimit:
    """Test that the periods query parameter limits results."""

    def test_periods_limits_data(self, client):
        """Setting periods=6 should return at most 6 data points per type."""
        resp = client.get("/api/comparison/accommodation-types?periods=6")
        assert resp.status_code == 200
        data = resp.json()
        for accom_type in ["rural", "hotel"]:
            assert len(data["types"][accom_type]["data"]) <= 6

    def test_periods_default_24(self, client):
        """Default periods should return up to 24 data points."""
        resp = client.get("/api/comparison/accommodation-types")
        data = resp.json()
        for accom_type in ["rural", "hotel"]:
            assert len(data["types"][accom_type]["data"]) <= 24

    def test_periods_1(self, client):
        """Setting periods=1 should return exactly 1 data point per type."""
        resp = client.get("/api/comparison/accommodation-types?periods=1")
        data = resp.json()
        for accom_type in ["rural", "hotel"]:
            assert len(data["types"][accom_type]["data"]) == 1

    def test_large_periods_returns_all_available(self, client):
        """Setting a large periods value should return all available data."""
        resp = client.get("/api/comparison/accommodation-types?periods=120")
        assert resp.status_code == 200
        data = resp.json()
        # Test data has 4 years * 12 months = 48 points
        for accom_type in ["rural", "hotel"]:
            assert len(data["types"][accom_type]["data"]) == 48
