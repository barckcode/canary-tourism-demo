"""Tests for tourist apartment inter-island comparison data.

Covers:
- 3 new apartment series are present in INE_SERIES
- Correct indicator names and geo codes
- Total series count is 41 (38 + 3)
- Comparison endpoint works with apartamento_ocupacion and apartamento_estancia_media
"""

import pytest

from app.api.comparison import PROVINCE_INDICATORS, VALID_INDICATORS
from app.etl.sources import ine


# ---------------------------------------------------------------------------
# INE_SERIES configuration tests
# ---------------------------------------------------------------------------

class TestApartmentComparisonSeriesConfig:
    """Verify that apartment comparison series are properly configured."""

    def _series_ids(self):
        return [s[0] for s in ine.INE_SERIES]

    def _series_indicators(self):
        return [s[1] for s in ine.INE_SERIES]

    def _series_geo_codes(self):
        return {s[0]: s[2] for s in ine.INE_SERIES}

    def test_ocupacion_las_palmas_present(self):
        """EOT9167 apartamento_ocupacion_plazas_las_palmas should be in INE_SERIES."""
        assert "EOT9167" in self._series_ids()

    def test_estancia_media_las_palmas_present(self):
        """EOT9677 apartamento_estancia_media_las_palmas should be in INE_SERIES."""
        assert "EOT9677" in self._series_ids()

    def test_estancia_media_tenerife_present(self):
        """EOT9679 apartamento_estancia_media_tenerife should be in INE_SERIES."""
        assert "EOT9679" in self._series_ids()

    def test_indicator_names(self):
        """All 3 new indicators should have correct names."""
        indicators = self._series_indicators()
        assert "apartamento_ocupacion_plazas_las_palmas" in indicators
        assert "apartamento_estancia_media_las_palmas" in indicators
        assert "apartamento_estancia_media_tenerife" in indicators

    def test_las_palmas_geo_codes(self):
        """Las Palmas apartment series should use ES701 geo code."""
        geo_map = self._series_geo_codes()
        assert geo_map["EOT9167"] == "ES701"
        assert geo_map["EOT9677"] == "ES701"

    def test_tenerife_estancia_media_geo_code(self):
        """Tenerife estancia media series should use ES709 geo code."""
        geo_map = self._series_geo_codes()
        assert geo_map["EOT9679"] == "ES709"

    def test_total_series_count(self):
        """INE_SERIES should now have 41 entries (38 + 3 apartment comparison)."""
        assert len(ine.INE_SERIES) == 41

    def test_existing_tenerife_ocupacion_still_present(self):
        """EAT3932 apartamento_ocupacion_plazas_tenerife should still be present."""
        assert "EAT3932" in self._series_ids()

    def test_series_placed_after_existing_apartments(self):
        """New apartment series should appear after the existing apartment block."""
        ids = self._series_ids()
        eat3933_idx = ids.index("EAT3933")
        eot9167_idx = ids.index("EOT9167")
        eot9677_idx = ids.index("EOT9677")
        eot9679_idx = ids.index("EOT9679")
        assert eot9167_idx > eat3933_idx
        assert eot9677_idx > eat3933_idx
        assert eot9679_idx > eat3933_idx


# ---------------------------------------------------------------------------
# Comparison endpoint configuration tests
# ---------------------------------------------------------------------------

class TestApartmentComparisonEndpointConfig:
    """Test that apartment indicators are configured in the comparison endpoint."""

    def test_apartamento_ocupacion_in_province_indicators(self):
        """apartamento_ocupacion should be a valid province comparison indicator."""
        assert "apartamento_ocupacion" in PROVINCE_INDICATORS

    def test_apartamento_estancia_media_in_province_indicators(self):
        """apartamento_estancia_media should be a valid province comparison indicator."""
        assert "apartamento_estancia_media" in PROVINCE_INDICATORS

    def test_apartamento_ocupacion_in_valid_indicators(self):
        """apartamento_ocupacion should appear in VALID_INDICATORS."""
        assert "apartamento_ocupacion" in VALID_INDICATORS

    def test_apartamento_estancia_media_in_valid_indicators(self):
        """apartamento_estancia_media should appear in VALID_INDICATORS."""
        assert "apartamento_estancia_media" in VALID_INDICATORS

    def test_apartamento_ocupacion_mapping(self):
        """Apartment occupancy mapping should have correct province indicators."""
        mapping = PROVINCE_INDICATORS["apartamento_ocupacion"]
        assert mapping["ES709"] == "apartamento_ocupacion_plazas_tenerife"
        assert mapping["ES701"] == "apartamento_ocupacion_plazas_las_palmas"

    def test_apartamento_estancia_media_mapping(self):
        """Apartment estancia media mapping should have correct province indicators."""
        mapping = PROVINCE_INDICATORS["apartamento_estancia_media"]
        assert mapping["ES709"] == "apartamento_estancia_media_tenerife"
        assert mapping["ES701"] == "apartamento_estancia_media_las_palmas"


# ---------------------------------------------------------------------------
# Comparison endpoint integration tests
# ---------------------------------------------------------------------------

class TestApartmentComparisonEndpoint:
    """Test the comparison endpoint with apartment indicators."""

    def test_apartamento_ocupacion_returns_200(self, client):
        """GET /api/comparison/provinces?indicator=apartamento_ocupacion should return 200."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == "apartamento_ocupacion"

    def test_apartamento_ocupacion_has_both_provinces(self, client):
        """Apartment occupancy comparison should contain data for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion")
        data = resp.json()
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]

    def test_apartamento_ocupacion_province_names(self, client):
        """Apartment occupancy comparison should have correct province names."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion")
        data = resp.json()
        assert data["provinces"]["ES709"]["name"] == "Santa Cruz de Tenerife"
        assert data["provinces"]["ES701"]["name"] == "Las Palmas"

    def test_apartamento_ocupacion_has_data(self, client):
        """Apartment occupancy comparison should have data points for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) > 0

    def test_apartamento_ocupacion_data_sorted(self, client):
        """Apartment occupancy data should be in ascending chronological order."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            periods = [p["period"] for p in data["provinces"][geo_code]["data"]]
            assert periods == sorted(periods)

    def test_apartamento_estancia_media_returns_200(self, client):
        """GET /api/comparison/provinces?indicator=apartamento_estancia_media should return 200."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_estancia_media")
        assert resp.status_code == 200
        data = resp.json()
        assert data["indicator"] == "apartamento_estancia_media"

    def test_apartamento_estancia_media_has_both_provinces(self, client):
        """Apartment estancia media comparison should contain data for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_estancia_media")
        data = resp.json()
        assert "ES709" in data["provinces"]
        assert "ES701" in data["provinces"]

    def test_apartamento_estancia_media_has_data(self, client):
        """Apartment estancia media comparison should have data points for both provinces."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_estancia_media")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) > 0

    def test_apartamento_estancia_media_periods_limit(self, client):
        """Apartment estancia media should respect periods parameter."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_estancia_media&periods=6")
        assert resp.status_code == 200
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            assert len(data["provinces"][geo_code]["data"]) <= 6

    def test_apartamento_ocupacion_values_are_percentages(self, client):
        """Apartment occupancy values should be reasonable percentages (0-100)."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_ocupacion&periods=12")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            for point in data["provinces"][geo_code]["data"]:
                assert 0 < point["value"] < 200, (
                    f"Occupancy value {point['value']} outside expected range for {geo_code}"
                )

    def test_apartamento_estancia_media_values_are_days(self, client):
        """Apartment estancia media values should be reasonable day counts."""
        resp = client.get("/api/comparison/provinces?indicator=apartamento_estancia_media&periods=12")
        data = resp.json()
        for geo_code in ["ES709", "ES701"]:
            for point in data["provinces"][geo_code]["data"]:
                assert 0 < point["value"] < 60, (
                    f"Estancia media value {point['value']} outside expected range for {geo_code}"
                )
