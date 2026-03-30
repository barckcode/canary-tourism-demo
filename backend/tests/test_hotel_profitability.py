"""Tests for hotel profitability indicators (ADR, RevPAR, IPH).

Covers:
- New series IDs are present in INE_SERIES with correct names and geo codes
- Total series count is 38 (32 + 6)
- Comparison endpoint works with indicator=adr and indicator=revpar
- Dashboard KPIs include iph_index and iph_variation fields
- Invalid comparison indicator still returns 400
"""

import pytest

from app.api.comparison import PROVINCE_INDICATORS, VALID_INDICATORS
from app.etl.sources import ine


# ---------------------------------------------------------------------------
# INE_SERIES configuration tests
# ---------------------------------------------------------------------------

class TestHotelProfitabilitySeriesConfig:
    """Verify that hotel profitability series are properly configured."""

    def _series_ids(self):
        return [s[0] for s in ine.INE_SERIES]

    def _series_indicators(self):
        return [s[1] for s in ine.INE_SERIES]

    def _series_geo_codes(self):
        return {s[0]: s[2] for s in ine.INE_SERIES}

    def test_adr_tenerife_present(self):
        """EOT43288 hotel_adr_tenerife should be in INE_SERIES."""
        assert "EOT43288" in self._series_ids()

    def test_adr_las_palmas_present(self):
        """EOT43289 hotel_adr_las_palmas should be in INE_SERIES."""
        assert "EOT43289" in self._series_ids()

    def test_revpar_tenerife_present(self):
        """EOT43691 hotel_revpar_tenerife should be in INE_SERIES."""
        assert "EOT43691" in self._series_ids()

    def test_revpar_las_palmas_present(self):
        """EOT43692 hotel_revpar_las_palmas should be in INE_SERIES."""
        assert "EOT43692" in self._series_ids()

    def test_iph_indice_present(self):
        """EOT14634 iph_indice_canarias should be in INE_SERIES."""
        assert "EOT14634" in self._series_ids()

    def test_iph_variacion_present(self):
        """EOT14635 iph_variacion_canarias should be in INE_SERIES."""
        assert "EOT14635" in self._series_ids()

    def test_indicator_names(self):
        """All 6 new indicators should have correct names."""
        indicators = self._series_indicators()
        assert "hotel_adr_tenerife" in indicators
        assert "hotel_adr_las_palmas" in indicators
        assert "hotel_revpar_tenerife" in indicators
        assert "hotel_revpar_las_palmas" in indicators
        assert "iph_indice_canarias" in indicators
        assert "iph_variacion_canarias" in indicators

    def test_adr_geo_codes(self):
        """ADR series should use correct province geo codes."""
        geo_map = self._series_geo_codes()
        assert geo_map["EOT43288"] == "ES709"
        assert geo_map["EOT43289"] == "ES701"

    def test_revpar_geo_codes(self):
        """RevPAR series should use correct province geo codes."""
        geo_map = self._series_geo_codes()
        assert geo_map["EOT43691"] == "ES709"
        assert geo_map["EOT43692"] == "ES701"

    def test_iph_geo_codes(self):
        """IPH series should use ES70 (Canarias CCAA level)."""
        geo_map = self._series_geo_codes()
        assert geo_map["EOT14634"] == "ES70"
        assert geo_map["EOT14635"] == "ES70"

    def test_total_series_count(self):
        """INE_SERIES should now have 41 entries (32 + 6 hotel profitability + 3 apartment comparison)."""
        assert len(ine.INE_SERIES) == 41


# ---------------------------------------------------------------------------
# Comparison endpoint tests for ADR and RevPAR
# ---------------------------------------------------------------------------

class TestComparisonADRRevPAR:
    """Test that the comparison endpoint supports adr and revpar indicators."""

    def test_adr_in_province_indicators(self):
        """ADR should be a valid province comparison indicator."""
        assert "adr" in PROVINCE_INDICATORS

    def test_revpar_in_province_indicators(self):
        """RevPAR should be a valid province comparison indicator."""
        assert "revpar" in PROVINCE_INDICATORS

    def test_adr_in_valid_indicators(self):
        """ADR should appear in VALID_INDICATORS list."""
        assert "adr" in VALID_INDICATORS

    def test_revpar_in_valid_indicators(self):
        """RevPAR should appear in VALID_INDICATORS list."""
        assert "revpar" in VALID_INDICATORS

    def test_adr_indicator_mapping(self):
        """ADR indicator mapping should have correct province indicators."""
        assert PROVINCE_INDICATORS["adr"]["ES709"] == "hotel_adr_tenerife"
        assert PROVINCE_INDICATORS["adr"]["ES701"] == "hotel_adr_las_palmas"

    def test_revpar_indicator_mapping(self):
        """RevPAR indicator mapping should have correct province indicators."""
        assert PROVINCE_INDICATORS["revpar"]["ES709"] == "hotel_revpar_tenerife"
        assert PROVINCE_INDICATORS["revpar"]["ES701"] == "hotel_revpar_las_palmas"

    def test_comparison_adr_returns_200(self, client):
        """GET /api/comparison/provinces?indicator=adr should return 200."""
        resp = client.get("/api/comparison/provinces?indicator=adr")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == "adr"

    def test_comparison_adr_has_both_provinces(self, client):
        """ADR comparison should contain data for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=adr")
        data = resp.json()
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]

    def test_comparison_adr_province_names(self, client):
        """ADR comparison should have correct province names."""
        resp = client.get("/api/comparison/provinces?indicator=adr")
        data = resp.json()
        assert data["provinces"]["ES709"]["name"] == "Santa Cruz de Tenerife"
        assert data["provinces"]["ES701"]["name"] == "Las Palmas"

    def test_comparison_adr_has_data(self, client):
        """ADR comparison should have data points for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=adr")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) > 0

    def test_comparison_revpar_returns_200(self, client):
        """GET /api/comparison/provinces?indicator=revpar should return 200."""
        resp = client.get("/api/comparison/provinces?indicator=revpar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == "revpar"

    def test_comparison_revpar_has_both_provinces(self, client):
        """RevPAR comparison should contain data for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=revpar")
        data = resp.json()
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]

    def test_comparison_revpar_has_data(self, client):
        """RevPAR comparison should have data points for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=revpar")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) > 0

    def test_invalid_indicator_still_returns_400(self, client):
        """An invalid indicator should still return HTTP 400."""
        resp = client.get("/api/comparison/provinces?indicator=nonexistent")
        assert resp.status_code == 400
        assert "Invalid indicator" in resp.json()["detail"]

    def test_comparison_adr_data_sorted_chronologically(self, client):
        """ADR data points should be in ascending chronological order."""
        resp = client.get("/api/comparison/provinces?indicator=adr")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            periods = [p["period"] for p in data["provinces"][geo_code]["data"]]
            assert periods == sorted(periods)

    def test_comparison_revpar_periods_limit(self, client):
        """RevPAR comparison should respect periods parameter."""
        resp = client.get("/api/comparison/provinces?indicator=revpar&periods=6")
        assert resp.status_code == 200
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) <= 6


# ---------------------------------------------------------------------------
# Dashboard KPI tests for IPH
# ---------------------------------------------------------------------------

class TestDashboardIPHKPIs:
    """Test that the dashboard KPIs endpoint returns IPH data."""

    def test_kpis_include_iph_index(self, client):
        """Dashboard KPIs should include iph_index field."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "iph_index" in data

    def test_kpis_include_iph_variation(self, client):
        """Dashboard KPIs should include iph_variation field."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "iph_variation" in data

    def test_kpis_iph_index_has_value(self, client):
        """IPH index should have a non-null value when data is available."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data["data_available"]:
            assert data["iph_index"] is not None
            assert data["iph_index"] > 0

    def test_kpis_iph_variation_has_value(self, client):
        """IPH variation should have a non-null value when data is available."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data["data_available"]:
            assert data["iph_variation"] is not None

    def test_kpis_iph_index_reasonable_range(self, client):
        """IPH index should be within a reasonable range (base 2008=100)."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data.get("iph_index") is not None:
            # IPH index base is 2008=100, current values ~150-250
            assert 100 <= data["iph_index"] <= 300, (
                f"iph_index {data['iph_index']} outside expected range"
            )

    def test_kpis_no_data_includes_iph_fields(self, client):
        """Even with no arrivals data, IPH fields should be in response schema."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        # The response should always contain these fields (may be None)
        assert "iph_index" in data
        assert "iph_variation" in data
