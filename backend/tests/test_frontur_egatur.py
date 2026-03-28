"""Tests for Frontur/Egatur INE integration.

Covers:
- New series IDs are present in INE_SERIES
- Response normalization handles both flat-list and wrapper-dict formats
- Dashboard KPIs endpoint returns spending fields
- Timeseries API can query Frontur/Egatur indicators
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.etl.sources import ine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Helper to run async functions in sync tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# INE_SERIES configuration tests
# ---------------------------------------------------------------------------

class TestFronturEgaturSeriesConfig:
    """Verify that Frontur/Egatur series are properly configured."""

    def _series_ids(self):
        return [s[0] for s in ine.INE_SERIES]

    def _series_indicators(self):
        return [s[1] for s in ine.INE_SERIES]

    def test_frontur_series_present(self):
        """Frontur tourist arrivals series should be in INE_SERIES."""
        assert "FREG349" in self._series_ids()

    def test_egatur_gasto_total_present(self):
        """Egatur total spending series should be in INE_SERIES."""
        assert "FREG531" in self._series_ids()

    def test_egatur_gasto_diario_present(self):
        """Egatur daily spending series should be in INE_SERIES."""
        assert "FREG529" in self._series_ids()

    def test_egatur_estancia_media_present(self):
        """Egatur average stay series should be in INE_SERIES."""
        assert "FREG803" in self._series_ids()

    def test_frontur_indicator_name(self):
        """Frontur indicator should have the correct name."""
        assert "frontur_turistas_canarias" in self._series_indicators()

    def test_egatur_indicator_names(self):
        """Egatur indicators should have the correct names."""
        indicators = self._series_indicators()
        assert "egatur_gasto_total_canarias" in indicators
        assert "egatur_gasto_medio_diario_canarias" in indicators
        assert "egatur_estancia_media_canarias" in indicators

    def test_frontur_egatur_geo_code(self):
        """Frontur/Egatur series should use ES70 (Canarias CCAA level)."""
        frontur_egatur_ids = {"FREG349", "FREG531", "FREG529", "FREG803"}
        for series_id, indicator, geo_code in ine.INE_SERIES:
            if series_id in frontur_egatur_ids:
                assert geo_code == "ES70", (
                    f"Series {series_id} should use ES70 geo_code, got {geo_code}"
                )

    def test_total_series_count(self):
        """INE_SERIES should include the 4 new Frontur/Egatur entries."""
        # Original entries + 4 Frontur/Egatur = 26
        assert len(ine.INE_SERIES) == 26


# ---------------------------------------------------------------------------
# Response normalization tests
# ---------------------------------------------------------------------------

class TestNormalizeSeriesResponse:
    """Test _normalize_series_response handles both INE API formats."""

    def test_flat_list_format(self):
        """Should return flat list as-is."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 100.0},
            {"Anyo": 2025, "FK_Periodo": 2, "Valor": 200.0},
        ]
        result = ine._normalize_series_response(data)
        assert result == data

    def test_wrapper_dict_format(self):
        """Should extract Data list from wrapper dict."""
        inner = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 1300000.0},
        ]
        data = {
            "COD": "FREG349",
            "Nombre": "Canarias. Turista. Dato base.",
            "FK_Unidad": 3,
            "FK_Escala": 1,
            "Data": inner,
        }
        result = ine._normalize_series_response(data)
        assert result == inner

    def test_empty_list(self):
        """Should return empty list for empty input."""
        assert ine._normalize_series_response([]) == []

    def test_dict_without_data_key(self):
        """Should return empty list for dict without Data key."""
        assert ine._normalize_series_response({"COD": "X"}) == []

    def test_none_input(self):
        """Should return empty list for None."""
        assert ine._normalize_series_response(None) == []

    def test_string_input(self):
        """Should return empty list for unexpected types."""
        assert ine._normalize_series_response("unexpected") == []


# ---------------------------------------------------------------------------
# Parsing tests for Frontur/Egatur data
# ---------------------------------------------------------------------------

class TestFronturEgaturParsing:
    """Test that Frontur/Egatur series data is parsed correctly."""

    def test_parse_frontur_records(self):
        """Should parse Frontur monthly tourist arrivals."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 1427922.0},
            {"Anyo": 2025, "FK_Periodo": 2, "Valor": 1444574.0},
        ]
        records = ine._parse_series_records(
            data, "frontur_turistas_canarias", "ES70"
        )
        assert len(records) == 2
        assert records[0]["source"] == "ine"
        assert records[0]["indicator"] == "frontur_turistas_canarias"
        assert records[0]["geo_code"] == "ES70"
        assert records[0]["period"] == "2025-01"
        assert records[0]["value"] == 1427922.0
        assert records[1]["period"] == "2025-02"

    def test_parse_egatur_daily_spending(self):
        """Should parse Egatur average daily spending."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 11, "Valor": 192.0},
            {"Anyo": 2025, "FK_Periodo": 12, "Valor": 190.0},
        ]
        records = ine._parse_series_records(
            data, "egatur_gasto_medio_diario_canarias", "ES70"
        )
        assert len(records) == 2
        assert records[0]["indicator"] == "egatur_gasto_medio_diario_canarias"
        assert records[0]["value"] == 192.0
        assert records[0]["period"] == "2025-11"

    def test_parse_egatur_avg_stay(self):
        """Should parse Egatur average stay duration."""
        data = [
            {"Anyo": 2026, "FK_Periodo": 1, "Valor": 8.12},
        ]
        records = ine._parse_series_records(
            data, "egatur_estancia_media_canarias", "ES70"
        )
        assert len(records) == 1
        assert records[0]["value"] == 8.12
        assert records[0]["period"] == "2026-01"

    def test_parse_skips_null_values(self):
        """Should skip records with None Valor."""
        data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": None},
            {"Anyo": 2025, "FK_Periodo": 2, "Valor": 1500000.0},
        ]
        records = ine._parse_series_records(
            data, "frontur_turistas_canarias", "ES70"
        )
        assert len(records) == 1


# ---------------------------------------------------------------------------
# Fetch with wrapper dict format
# ---------------------------------------------------------------------------

class TestFetchWithWrapperFormat:
    """Test that fetch functions handle the wrapper dict response format."""

    def test_fetch_series_data_wrapper_dict(self):
        """_fetch_series_data should normalize wrapper dict to flat list."""
        inner_data = [
            {"Anyo": 2025, "FK_Periodo": 1, "Valor": 1427922.0},
        ]
        wrapper = {
            "COD": "FREG349",
            "Nombre": "Canarias. Turista. Dato base.",
            "Data": inner_data,
        }

        mock_response = MagicMock()
        mock_response.json.return_value = wrapper

        async def mock_fetch(*args, **kwargs):
            return mock_response

        with patch("app.etl.sources.ine.async_fetch_with_retry", mock_fetch):
            import httpx
            async def run():
                async with httpx.AsyncClient() as client:
                    return await ine._fetch_series_data(client, "FREG349")
            result = _run_async(run())

        assert result == inner_data

    def test_fetch_latest_period_wrapper_dict(self):
        """_fetch_latest_period should normalize wrapper dict."""
        inner_data = [
            {"Anyo": 2026, "FK_Periodo": 1, "Valor": 1427922.0},
        ]
        wrapper = {"COD": "FREG349", "Data": inner_data}

        mock_response = MagicMock()
        mock_response.json.return_value = wrapper

        async def mock_fetch(*args, **kwargs):
            return mock_response

        with patch("app.etl.sources.ine.async_fetch_with_retry", mock_fetch):
            import httpx
            async def run():
                async with httpx.AsyncClient() as client:
                    return await ine._fetch_latest_period(client, "FREG349")
            result = _run_async(run())

        assert result == inner_data[0]

    def test_fetch_series_with_frontur_mock(self):
        """Should fetch and parse a full Frontur series via wrapper format."""
        wrapper = {
            "COD": "FREG349",
            "Data": [
                {"Anyo": 2025, "FK_Periodo": 1, "Valor": 1427922.0},
                {"Anyo": 2025, "FK_Periodo": 2, "Valor": 1444574.0},
            ],
        }

        mock_response = MagicMock()
        mock_response.json.return_value = wrapper

        async def mock_fetch(*args, **kwargs):
            return mock_response

        with patch("app.etl.sources.ine.async_fetch_with_retry", mock_fetch):
            series = [("FREG349", "frontur_turistas_canarias", "ES70")]
            records = _run_async(ine.fetch_series(series))

        assert len(records) == 2
        assert records[0]["indicator"] == "frontur_turistas_canarias"
        assert records[0]["geo_code"] == "ES70"
        assert records[0]["value"] == 1427922.0


# ---------------------------------------------------------------------------
# Dashboard KPI endpoint tests
# ---------------------------------------------------------------------------

class TestDashboardSpendingKPIs:
    """Test that the dashboard KPIs endpoint returns spending data."""

    def test_kpis_include_daily_spend(self, client):
        """Dashboard KPIs should include daily_spend from Egatur."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_spend" in data
        if data["data_available"]:
            assert data["daily_spend"] is not None
            assert data["daily_spend"] > 0

    def test_kpis_include_avg_stay_ine(self, client):
        """Dashboard KPIs should include avg_stay_ine from Egatur."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_stay_ine" in data
        if data["data_available"]:
            assert data["avg_stay_ine"] is not None
            assert data["avg_stay_ine"] > 0

    def test_kpis_include_yoy_fields(self, client):
        """Dashboard KPIs should include YoY change fields for spending."""
        resp = client.get("/api/dashboard/kpis")
        assert resp.status_code == 200
        data = resp.json()
        # These fields should exist in the response schema
        assert "daily_spend_yoy" in data
        assert "avg_stay_ine_yoy" in data

    def test_kpis_spending_values_reasonable(self, client):
        """Spending KPI values should be within expected ranges."""
        resp = client.get("/api/dashboard/kpis")
        data = resp.json()
        if data.get("daily_spend") is not None:
            # Daily spend should be between 50 and 500 euros
            assert 50 <= data["daily_spend"] <= 500, (
                f"daily_spend {data['daily_spend']} outside expected range"
            )
        if data.get("avg_stay_ine") is not None:
            # Average stay should be between 1 and 30 days
            assert 1 <= data["avg_stay_ine"] <= 30, (
                f"avg_stay_ine {data['avg_stay_ine']} outside expected range"
            )


# ---------------------------------------------------------------------------
# Timeseries API query tests
# ---------------------------------------------------------------------------

class TestTimeseriesAPIFronturEgatur:
    """Test that Frontur/Egatur indicators can be queried via timeseries API."""

    @pytest.mark.parametrize("indicator", [
        "frontur_turistas_canarias",
        "egatur_gasto_total_canarias",
        "egatur_gasto_medio_diario_canarias",
        "egatur_estancia_media_canarias",
    ])
    def test_query_frontur_egatur_indicator(self, client, indicator):
        """Each Frontur/Egatur indicator should be queryable."""
        resp = client.get(
            "/api/timeseries",
            params={"indicator": indicator, "geo": "ES70"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_frontur_data_has_sufficient_history(self, client):
        """Frontur series should have at least 36 months for forecasting."""
        resp = client.get(
            "/api/timeseries",
            params={"indicator": "frontur_turistas_canarias", "geo": "ES70"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["total"] >= 36
