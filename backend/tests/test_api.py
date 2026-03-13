"""Integration tests for all API endpoints."""


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
    assert data["latest_arrivals"] > 100_000


def test_dashboard_kpis_yoy_change(client):
    """YoY change should be a reasonable percentage."""
    r = client.get("/api/dashboard/kpis")
    data = r.json()
    if "yoy_change" in data:
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


# --- Time Series ---

def test_timeseries_query_turistas(client):
    """Query turistas indicator should return non-empty data."""
    r = client.get("/api/timeseries?indicator=turistas&geo=ES709")
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) > 100
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
    assert len(data) > 5
    ids = [d["id"] for d in data]
    assert "turistas" in ids


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


def test_predictions_compare(client):
    """Compare endpoint should return multiple models."""
    r = client.get("/api/predictions/compare?indicator=turistas")
    assert r.status_code == 200
    models = r.json()["models"]
    assert "sarima" in models
    assert "ensemble" in models
    assert "holt_winters" in models
    assert "seasonal_naive" in models


# --- Profiles ---

def test_profiles_list(client):
    """Should return 4 tourist profile clusters."""
    r = client.get("/api/profiles")
    assert r.status_code == 200
    clusters = r.json()["clusters"]
    assert len(clusters) == 4
    for c in clusters:
        assert "id" in c
        assert "name" in c
        assert "size_pct" in c
        assert c["size_pct"] > 0


def test_profile_detail(client):
    """Cluster detail should include spending and activities."""
    r = client.get("/api/profiles/0")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "avg_spend" in data
    assert "top_activities" in data
    assert "top_motivations" in data
    assert "characteristics" in data


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
