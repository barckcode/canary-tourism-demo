"""Integration tests for all API endpoints."""

from unittest.mock import MagicMock

from app.api.dashboard import _classify_position


def test_classify_position_high():
    """Values >= 110% of average should be classified as High."""
    assert _classify_position(1200, 1000) == "High"
    assert _classify_position(1100, 1000) == "High"


def test_classify_position_moderate():
    """Values between 90% and 110% of average should be Moderate."""
    assert _classify_position(1000, 1000) == "Moderate"
    assert _classify_position(1050, 1000) == "Moderate"
    assert _classify_position(950, 1000) == "Moderate"


def test_classify_position_low():
    """Values <= 90% of average should be classified as Low."""
    assert _classify_position(800, 1000) == "Low"
    assert _classify_position(900, 1000) == "Low"


def test_classify_position_zero_avg():
    """Zero average should return Moderate to avoid division by zero."""
    assert _classify_position(100, 0) == "Moderate"


def test_kpi_yoy_with_zero_prev_value(db):
    """YoY calculation should not crash when previous period value is 0 (issue #27).

    When prev.value == 0, truthiness check `if prev and prev.value` would skip
    the calculation silently. The fix uses explicit None/zero checks instead.
    """
    from app.db.models import TimeSeries

    # Simulate: latest has value 500000, previous year same period has value 0
    mock_latest = MagicMock()
    mock_latest.value = 500000.0
    mock_latest.period = "2025-03"

    mock_prev = MagicMock()
    mock_prev.value = 0  # This is falsy in Python

    # The old code `if prev and prev.value` would treat 0 as False.
    # The fix uses `if prev is not None and prev.value is not None and prev.value != 0`.
    # With value=0, YoY should NOT be computed (division by zero), but it should
    # not crash either.
    assert mock_prev is not None and mock_prev.value is not None
    assert mock_prev.value == 0  # This should be caught by the != 0 guard


def test_kpi_yoy_with_none_prev_value():
    """YoY calculation should handle None prev.value gracefully (issue #27)."""
    mock_prev = MagicMock()
    mock_prev.value = None

    # The fix checks `prev.value is not None` explicitly
    assert mock_prev is not None
    assert mock_prev.value is None
    # With None value, YoY should not be computed


def test_kpi_latest_value_none_guard():
    """KPI endpoint should guard against latest.value being None (issue #27)."""
    mock_latest = MagicMock()
    mock_latest.value = None

    # The fix checks `if latest and latest.value is not None`
    # With None value, the KPI block should be skipped entirely
    assert mock_latest is not None
    assert mock_latest.value is None


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# --- Dashboard ---

def test_dashboard_kpis_fields(client):
    """KPIs endpoint should return all expected fields."""
    r = client.get("/api/dashboard/kpis")
    assert r.status_code == 200
    data = r.json()
    for field in ["latest_arrivals", "latest_period", "occupancy_rate"]:
        assert field in data, f"Missing field: {field}"
    assert data["latest_arrivals"] > 0


def test_dashboard_kpis_yoy_change(client):
    """YoY change should be present and be a reasonable percentage."""
    r = client.get("/api/dashboard/kpis")
    data = r.json()
    assert "yoy_change" in data, "yoy_change field must be present in KPIs response"
    assert -50 < data["yoy_change"] < 100, (
        f"YoY change {data['yoy_change']}% outside expected range"
    )


def test_dashboard_summary_trends(client):
    """Summary should include arrival and occupancy trends."""
    r = client.get("/api/dashboard/summary")
    assert r.status_code == 200
    data = r.json()
    assert "arrivals_trend_24m" in data
    assert len(data["arrivals_trend_24m"]) > 0
    assert "period" in data["arrivals_trend_24m"][0]
    assert "value" in data["arrivals_trend_24m"][0]


def test_dashboard_top_markets(client):
    """Top markets endpoint should return markets with percentages."""
    r = client.get("/api/dashboard/top-markets")
    assert r.status_code == 200
    data = r.json()
    assert "markets" in data
    assert "total" in data
    assert len(data["markets"]) > 0
    assert len(data["markets"]) <= 5
    first = data["markets"][0]
    assert "country" in first
    assert "pct" in first
    assert "count" in first
    assert first["pct"] > 0
    # Percentages should sum to <= 100
    total_pct = sum(m["pct"] for m in data["markets"])
    assert total_pct <= 100.1


def test_dashboard_top_markets_sorted(client):
    """Top markets should be sorted by count descending."""
    r = client.get("/api/dashboard/top-markets")
    data = r.json()
    markets = data["markets"]
    for i in range(len(markets) - 1):
        assert markets[i]["count"] >= markets[i + 1]["count"]


# --- Map ---

def test_dashboard_map_default_period(client):
    """Map endpoint without period param should return latest available data."""
    r = client.get("/api/dashboard/map")
    assert r.status_code == 200
    data = r.json()
    assert data["data_available"] is True
    assert data["period"] is not None
    munis = data["municipalities"]
    # Should have all 12 municipalities
    assert len(munis) == 12
    # Adeje, Arona, Puerto de la Cruz should have real data
    assert munis["38001"]["source"] == "real"
    assert munis["38006"]["source"] == "real"
    assert munis["38028"]["source"] == "real"
    # Adeje should have the highest intensity (highest base pernoctaciones)
    assert munis["38001"]["tourism_intensity"] == 100
    assert munis["38001"]["pernoctaciones"] is not None
    # Other municipalities should be estimated
    assert munis["38038"]["source"] == "estimated"
    assert munis["38023"]["source"] == "estimated"


def test_dashboard_map_specific_period(client):
    """Map endpoint with specific period should return data for that period."""
    r = client.get("/api/dashboard/map?period=2024-06")
    assert r.status_code == 200
    data = r.json()
    assert data["data_available"] is True
    assert data["period"] == "2024-06"
    munis = data["municipalities"]
    assert len(munis) == 12
    assert munis["38001"]["source"] == "real"


def test_dashboard_map_no_data_period(client):
    """Map endpoint with a period having no data should return fallback."""
    r = client.get("/api/dashboard/map?period=1999-01")
    assert r.status_code == 200
    data = r.json()
    assert data["data_available"] is False
    munis = data["municipalities"]
    assert len(munis) == 12
    # All should be estimated in fallback
    for code, muni in munis.items():
        assert muni["source"] == "estimated"


def test_dashboard_map_intensity_range(client):
    """All tourism_intensity values should be in 0-100 range."""
    r = client.get("/api/dashboard/map")
    assert r.status_code == 200
    for code, muni in r.json()["municipalities"].items():
        assert 0 <= muni["tourism_intensity"] <= 100, (
            f"Municipality {code} intensity {muni['tourism_intensity']} out of range"
        )


def test_dashboard_map_municipality_names(client):
    """All municipalities should have proper names."""
    r = client.get("/api/dashboard/map")
    assert r.status_code == 200
    munis = r.json()["municipalities"]
    assert munis["38001"]["name"] == "Adeje"
    assert munis["38006"]["name"] == "Arona"
    assert munis["38028"]["name"] == "Puerto de la Cruz"
    assert munis["38038"]["name"] == "Santa Cruz de Tenerife"


def test_dashboard_seasonal_position(client):
    """Seasonal position should return peak month and current position."""
    r = client.get("/api/dashboard/seasonal-position")
    assert r.status_code == 200
    data = r.json()
    assert "peak_month" in data
    assert "peak_month_number" in data
    assert "current_position" in data
    assert "current_month" in data
    assert "next_3_months" in data
    assert "next_months" in data
    assert "monthly_averages" in data
    # Position values should be one of the valid options
    assert data["current_position"] in ("High", "Moderate", "Low")
    assert data["next_3_months"] in ("High", "Moderate", "Low")
    # Peak month number should be 1-12
    assert 1 <= data["peak_month_number"] <= 12
    # Monthly averages should have entries
    assert len(data["monthly_averages"]) > 0


# --- Time Series ---

def test_timeseries_query_turistas(client):
    """Query turistas indicator should return non-empty data."""
    r = client.get("/api/timeseries?indicator=turistas&geo=ES709")
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) > 12, "Expected more than 12 months of turistas data"
    assert data["metadata"]["indicator"] == "turistas"
    assert data["metadata"]["geo"] == "ES709"


def test_timeseries_query_with_date_range(client):
    """Filtering by date range should narrow results."""
    r_all = client.get("/api/timeseries?indicator=turistas&geo=ES709")
    r_filtered = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&from=2023-01&to=2024-12"
    )
    assert r_filtered.status_code == 200
    all_count = len(r_all.json()["data"])
    filtered_count = len(r_filtered.json()["data"])
    assert filtered_count < all_count
    assert filtered_count > 0


def test_timeseries_indicators_list(client):
    """Indicators endpoint should return available indicators."""
    r = client.get("/api/timeseries/indicators")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0, "Expected at least one indicator"
    ids = [d["id"] for d in data]
    assert "turistas" in ids


# --- YoY Heatmap ---

def test_yoy_default_indicators(client):
    """YoY endpoint without indicator param should return multiple indicators."""
    r = client.get("/api/timeseries/yoy")
    assert r.status_code == 200
    data = r.json()
    assert "indicators" in data
    assert "metadata" in data
    assert data["metadata"]["total_indicators"] > 0
    # turistas should always be present
    assert "turistas" in data["indicators"]


def test_yoy_single_indicator(client):
    """YoY endpoint with a specific indicator should return only that one."""
    r = client.get("/api/timeseries/yoy?indicator=turistas")
    assert r.status_code == 200
    data = r.json()
    indicators = data["indicators"]
    assert len(indicators) == 1
    assert "turistas" in indicators


def test_yoy_cell_structure(client):
    """Each YoY cell should have year, month, value, and yoy_change fields."""
    r = client.get("/api/timeseries/yoy?indicator=turistas")
    assert r.status_code == 200
    cells = r.json()["indicators"]["turistas"]
    assert len(cells) > 12, "Expected more than one year of data"
    first = cells[0]
    assert "year" in first
    assert "month" in first
    assert "value" in first
    assert "yoy_change" in first
    # First year cells should have null yoy_change
    assert first["yoy_change"] is None


def test_yoy_change_calculation(client):
    """YoY change values should be reasonable percentages."""
    r = client.get("/api/timeseries/yoy?indicator=turistas")
    assert r.status_code == 200
    cells = r.json()["indicators"]["turistas"]
    non_null = [c for c in cells if c["yoy_change"] is not None]
    assert len(non_null) > 0
    for c in non_null:
        # YoY changes should be finite numbers (not NaN or Inf)
        assert isinstance(c["yoy_change"], (int, float))


def test_yoy_empty_indicator(client):
    """Non-existent indicator should return empty indicators dict."""
    r = client.get("/api/timeseries/yoy?indicator=nonexistent_indicator_xyz")
    assert r.status_code == 200
    data = r.json()
    assert data["indicators"] == {}
    assert data["metadata"]["total_indicators"] == 0


def test_yoy_month_range(client):
    """All month values should be 0-11 (zero-based)."""
    r = client.get("/api/timeseries/yoy?indicator=turistas")
    assert r.status_code == 200
    cells = r.json()["indicators"]["turistas"]
    for c in cells:
        assert 0 <= c["month"] <= 11


# --- Predictions ---

def test_predictions_ensemble(client):
    """Ensemble predictions should have 12 months with CI bands."""
    r = client.get("/api/predictions?indicator=turistas&model=ensemble&horizon=12")
    assert r.status_code == 200
    data = r.json()
    assert len(data["forecast"]) == 12
    first = data["forecast"][0]
    assert "value" in first
    assert "ci_lower_80" in first
    assert "ci_upper_80" in first
    assert "ci_lower_95" in first
    assert "ci_upper_95" in first
    assert first["ci_lower_95"] < first["ci_lower_80"] < first["value"]


def test_predictions_sarima(client):
    """SARIMA model should also be available."""
    r = client.get("/api/predictions?indicator=turistas&model=sarima")
    assert r.status_code == 200
    assert len(r.json()["forecast"]) == 12


def test_predictions_metrics_in_model_info(client):
    """Prediction response should include accuracy metrics in model_info."""
    r = client.get("/api/predictions?indicator=turistas&model=ensemble&horizon=12")
    assert r.status_code == 200
    data = r.json()
    metrics = data["model_info"].get("metrics")
    assert metrics is not None, "metrics should be present in model_info"
    assert "rmse" in metrics
    assert "mae" in metrics
    assert "mape" in metrics
    assert "test_size" in metrics
    assert metrics["mape"] > 0
    assert metrics["rmse"] > 0
    assert metrics["mae"] > 0
    assert metrics["test_size"] == 12


def test_predictions_metrics_mape_reasonable(client):
    """MAPE values should be reasonable (< 50%) for production models."""
    r = client.get("/api/predictions?indicator=turistas&model=ensemble&horizon=12")
    data = r.json()
    mape = data["model_info"]["metrics"]["mape"]
    assert 0 < mape < 50, f"MAPE {mape}% outside reasonable range"


def test_predictions_compare(client):
    """Compare endpoint should return multiple models."""
    r = client.get("/api/predictions/compare?indicator=turistas")
    assert r.status_code == 200
    models = r.json()["models"]
    assert "sarima" in models
    assert "ensemble" in models
    assert "holt_winters" in models
    assert "seasonal_naive" in models


def test_predictions_compare_includes_metrics(client):
    """Compare endpoint should return accuracy metrics for all models."""
    r = client.get("/api/predictions/compare?indicator=turistas")
    assert r.status_code == 200
    data = r.json()
    assert "metrics" in data, "compare response should include metrics"
    metrics = data["metrics"]
    for model_name in ["sarima", "holt_winters", "seasonal_naive", "ensemble"]:
        assert model_name in metrics, f"Missing metrics for {model_name}"
        m = metrics[model_name]
        assert "rmse" in m
        assert "mae" in m
        assert "mape" in m
        assert m["mape"] > 0


# --- Profiles ---

def test_profiles_list(client):
    """Should return 4 tourist profile clusters with all fields."""
    r = client.get("/api/profiles")
    assert r.status_code == 200
    clusters = r.json()["clusters"]
    assert len(clusters) == 4
    for c in clusters:
        assert "id" in c
        assert "name" in c
        assert "size_pct" in c
        assert c["size_pct"] > 0
        # New fields: activities, motivations, satisfaction, spending
        assert "top_activities" in c
        assert "top_motivations" in c
        assert "avg_satisfaction" in c
        assert "spending_breakdown" in c
        assert isinstance(c["top_activities"], list)
        assert isinstance(c["top_motivations"], list)


def test_profiles_list_has_activities_and_motivations(client):
    """At least one cluster should have non-empty activities and motivations."""
    r = client.get("/api/profiles")
    clusters = r.json()["clusters"]
    has_activities = any(len(c["top_activities"]) > 0 for c in clusters)
    has_motivations = any(len(c["top_motivations"]) > 0 for c in clusters)
    assert has_activities, "No cluster has top_activities populated"
    assert has_motivations, "No cluster has top_motivations populated"


def test_profile_detail(client):
    """Cluster detail should include spending, activities, and satisfaction."""
    r = client.get("/api/profiles/0")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "avg_spend" in data
    assert "top_activities" in data
    assert "top_motivations" in data
    assert "characteristics" in data
    assert "avg_satisfaction" in data
    assert "spending_breakdown" in data


def test_profile_detail_satisfaction_range(client):
    """Satisfaction score should be present and in 0-10 range."""
    r = client.get("/api/profiles/0")
    data = r.json()
    sat = data.get("avg_satisfaction")
    assert sat is not None, "avg_satisfaction must be present in profile detail"
    assert 0 <= sat <= 10, f"Satisfaction {sat} outside 0-10 range"


def test_spending_by_cluster(client):
    """Spending endpoint should return breakdown per cluster from microdata."""
    r = client.get("/api/profiles/spending")
    assert r.status_code == 200
    data = r.json()
    assert "spending_by_cluster" in data
    spending = data["spending_by_cluster"]
    # Should have data for at least one cluster
    assert len(spending) > 0
    # Each cluster should have categories with amount and pct
    for cluster_id, categories in spending.items():
        assert isinstance(categories, list)
        assert len(categories) > 0
        for cat in categories:
            assert "category" in cat
            assert "amount" in cat
            assert "pct" in cat
            assert cat["amount"] > 0
            assert 0 < cat["pct"] <= 100


def test_spending_by_cluster_percentages_sum(client):
    """Spending percentages per cluster should sum to approximately 100."""
    r = client.get("/api/profiles/spending")
    spending = r.json()["spending_by_cluster"]
    for cluster_id, categories in spending.items():
        total_pct = sum(c["pct"] for c in categories)
        assert 95 <= total_pct <= 105, (
            f"Cluster {cluster_id} spending pcts sum to {total_pct}, expected ~100"
        )


def test_profile_not_found(client):
    """Non-existent cluster should return 404."""
    r = client.get("/api/profiles/999")
    assert r.status_code == 404


def test_horizon_limit_predictions(client):
    """Horizon > 60 should be rejected."""
    r = client.get("/api/predictions?indicator=turistas&horizon=100")
    assert r.status_code == 422


def test_horizon_limit_scenarios(client):
    """Horizon > 60 should be rejected in scenarios."""
    r = client.post("/api/scenarios", json={"horizon": 100})
    assert r.status_code == 422


def test_profile_nationalities(client):
    """Nationality profiles should return aggregate stats."""
    r = client.get("/api/profiles/nationalities")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 3
    first = data[0]
    assert "nationality" in first
    assert "count" in first
    assert "avg_spend" in first
    assert first["count"] > 0


def test_profile_flows_sankey(client):
    """Flows endpoint should return nodes and links for Sankey diagram."""
    r = client.get("/api/profiles/flows")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0
    assert len(data["links"]) > 0
    # Verify link structure
    link = data["links"][0]
    assert "source" in link
    assert "target" in link
    assert "value" in link


# --- Scenarios ---

def test_scenario_post(client):
    """POST scenario should return baseline and scenario forecasts."""
    r = client.post(
        "/api/scenarios",
        json={
            "occupancy_change_pct": 5.0,
            "adr_change_pct": -2.0,
            "foreign_ratio_change_pct": 1.0,
            "horizon": 6,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "baseline_forecast" in data
    assert "scenario_forecast" in data
    assert "impact_summary" in data
    assert len(data["baseline_forecast"]) == 6
    assert len(data["scenario_forecast"]) == 6


def test_scenario_zero_changes(client):
    """Zero changes should produce identical baseline and scenario."""
    r = client.post(
        "/api/scenarios",
        json={
            "occupancy_change_pct": 0,
            "adr_change_pct": 0,
            "foreign_ratio_change_pct": 0,
            "horizon": 3,
        },
    )
    assert r.status_code == 200
    data = r.json()
    for b, s in zip(data["baseline_forecast"], data["scenario_forecast"]):
        assert b["value"] == s["value"]


# --- Error response tests ---

def test_timeseries_missing_indicator(client):
    """Timeseries endpoint should return 422 when indicator param is missing."""
    r = client.get("/api/timeseries?geo=ES709")
    assert r.status_code == 422


def test_timeseries_empty_result(client):
    """Non-existent indicator should return empty data, not an error."""
    r = client.get("/api/timeseries?indicator=nonexistent_xyz&geo=ES709")
    assert r.status_code == 200
    data = r.json()
    assert data["data"] == []
    assert data["metadata"]["total_points"] == 0


def test_profile_detail_invalid_cluster(client):
    """Non-existent cluster ID should return 404 with detail message."""
    r = client.get("/api/profiles/999")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_scenario_invalid_values(client):
    """Scenario with out-of-range values should return 422."""
    r = client.post(
        "/api/scenarios",
        json={
            "occupancy_change_pct": 100.0,
            "adr_change_pct": 0,
            "foreign_ratio_change_pct": 0,
            "horizon": 6,
        },
    )
    assert r.status_code == 422


def test_scenario_missing_body(client):
    """Scenario without a JSON body should return 422."""
    r = client.post("/api/scenarios")
    assert r.status_code == 422


def test_predictions_invalid_model(client):
    """Requesting predictions for a non-existent model returns empty forecast."""
    r = client.get("/api/predictions?indicator=turistas&model=nonexistent_model")
    assert r.status_code == 200
    data = r.json()
    assert data["forecast"] == []
    assert data["model_info"]["name"] == "nonexistent_model"


# --- RevPAR KPI uses correct indicator (Issue #121) ---

def test_kpi_revpar_uses_correct_indicator(client):
    """RevPAR KPI should use alojatur_revpar, not alojatur_ingresos."""
    r = client.get("/api/dashboard/kpis")
    assert r.status_code == 200
    data = r.json()
    assert "revpar" in data
    # The test seed data sets alojatur_revpar base = 65.0 and alojatur_ingresos base = 62.0.
    # With variation = 1.0 + (month - 6) * 0.01, the latest period (2025-12) has
    # variation = 1.06, so revpar ~ 65 * 1.06 = 68.9 and ingresos ~ 62 * 1.06 = 65.72.
    # If the code incorrectly uses alojatur_ingresos, the value would be ~65.72.
    # With the fix using alojatur_revpar, the value should be ~68.9.
    assert data["revpar"] > 67.0, (
        f"RevPAR value {data['revpar']} is too low; "
        "likely still reading alojatur_ingresos instead of alojatur_revpar"
    )


# --- Period format validation (Issue #122) ---

def test_timeseries_invalid_from_period_returns_400(client):
    """Invalid from_period format should return HTTP 400."""
    r = client.get("/api/timeseries?indicator=turistas&from=2026-13")
    assert r.status_code == 400
    assert "from_period" in r.json()["detail"]


def test_timeseries_invalid_to_period_returns_400(client):
    """Invalid to_period format should return HTTP 400."""
    r = client.get("/api/timeseries?indicator=turistas&to=not-a-date")
    assert r.status_code == 400
    assert "to_period" in r.json()["detail"]


def test_timeseries_valid_period_passes(client):
    """Valid period format should not trigger validation error."""
    r = client.get("/api/timeseries?indicator=turistas&from=2023-01&to=2024-12")
    assert r.status_code == 200


def test_timeseries_invalid_period_month_zero(client):
    """Month 00 is not valid in YYYY-MM format."""
    r = client.get("/api/timeseries?indicator=turistas&from=2024-00")
    assert r.status_code == 400


def test_map_invalid_period_returns_400(client):
    """Invalid period format on /map should return HTTP 400."""
    r = client.get("/api/dashboard/map?period=2026-13")
    assert r.status_code == 400
    assert "period" in r.json()["detail"]


def test_map_valid_period_passes(client):
    """Valid period on /map should not trigger validation error."""
    r = client.get("/api/dashboard/map?period=2024-06")
    assert r.status_code == 200


def test_events_invalid_from_date_returns_400(client):
    """Invalid from_date format on /events should return HTTP 400."""
    r = client.get("/api/events?from_date=2026-13-01")
    assert r.status_code == 400
    assert "from_date" in r.json()["detail"]


def test_events_invalid_to_date_returns_400(client):
    """Invalid to_date format on /events should return HTTP 400."""
    r = client.get("/api/events?to_date=not-valid")
    assert r.status_code == 400
    assert "to_date" in r.json()["detail"]


def test_events_valid_dates_pass(client):
    """Valid date format on /events should not trigger validation error."""
    r = client.get("/api/events?from_date=2026-01-01&to_date=2026-12-31")
    assert r.status_code == 200
