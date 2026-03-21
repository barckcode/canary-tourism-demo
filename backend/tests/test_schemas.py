"""Tests for Pydantic response models in app.api.schemas."""

from app.api.schemas import (
    DashboardKPIsResponse,
    DashboardSummaryResponse,
    FlowsResponse,
    IndicatorInfo,
    NationalityProfileEntry,
    PredictionCompareResponse,
    PredictionResponse,
    ProfileDetailResponse,
    ProfilesListResponse,
    ScenarioResponse,
    SeasonalPositionResponse,
    SpendingByClusterResponse,
    TimeSeriesResponse,
    TopMarketsResponse,
    YoYResponse,
)


def test_dashboard_kpis_response_minimal():
    """KPIs response should accept minimal required fields."""
    r = DashboardKPIsResponse(latest_arrivals=500000, latest_period="2025-01")
    assert r.latest_arrivals == 500000
    assert r.yoy_change is None


def test_dashboard_summary_response():
    r = DashboardSummaryResponse(
        arrivals_trend_24m=[{"period": "2024-01", "value": 100}],
        occupancy_trend_12m=[],
        forecast=[],
    )
    assert len(r.arrivals_trend_24m) == 1


def test_timeseries_response():
    r = TimeSeriesResponse(
        data=[{"period": "2024-01", "value": 42}],
        metadata={"indicator": "turistas", "geo": "ES709", "measure": "ABSOLUTE", "total_points": 1},
    )
    assert r.metadata.total_points == 1


def test_prediction_response():
    r = PredictionResponse(
        forecast=[{"period": "2025-01", "value": 1000, "ci_lower_80": 900, "ci_upper_80": 1100}],
        model_info={"name": "ensemble", "total_periods": 1, "metrics": None},
        requested_horizon=12,
        actual_horizon=1,
        complete=False,
    )
    assert r.model_info.name == "ensemble"
    assert r.requested_horizon == 12
    assert r.actual_horizon == 1
    assert r.complete is False


def test_prediction_compare_response():
    r = PredictionCompareResponse(
        models={"sarima": [{"period": "2025-01", "value": 1000}]},
        metrics={"sarima": {"rmse": 100, "mae": 80, "mape": 5}},
    )
    assert "sarima" in r.models


def test_profiles_list_response():
    r = ProfilesListResponse(
        clusters=[{
            "id": 0, "name": "Budget", "size_pct": 25.0,
            "top_nationalities": [], "top_accommodations": [],
            "top_activities": [], "top_motivations": [],
        }]
    )
    assert len(r.clusters) == 1


def test_profile_detail_response():
    r = ProfileDetailResponse(
        id=0, name="Budget", size_pct=25.0,
        top_nationalities=[], top_accommodations=[],
        top_activities=[], top_motivations=[],
        characteristics={"avg_satisfaction": 8.5},
    )
    assert r.characteristics["avg_satisfaction"] == 8.5


def test_nationality_profile_entry():
    r = NationalityProfileEntry(nationality="UK", count=100, avg_spend=1500.0)
    assert r.avg_nights is None


def test_flows_response():
    r = FlowsResponse(
        nodes=[{"id": "country_826", "label": "UK"}],
        links=[{"source": "country_826", "target": "accom_HOTEL", "value": 50}],
    )
    assert len(r.nodes) == 1


def test_spending_by_cluster_response():
    r = SpendingByClusterResponse(
        spending_by_cluster={"0": [{"category": "Restaurant", "amount": 100, "pct": 50}]}
    )
    assert len(r.spending_by_cluster["0"]) == 1


def test_scenario_response():
    r = ScenarioResponse(
        baseline_forecast=[{"period": "2025-01", "value": 500000}],
        scenario_forecast=[{"period": "2025-01", "value": 510000}],
        impact_summary={"avg_baseline": 500000, "avg_scenario": 510000, "avg_change_pct": 2.0},
        params={"occupancy_change_pct": 5.0, "adr_change_pct": 0, "foreign_ratio_change_pct": 0},
    )
    assert len(r.baseline_forecast) == 1


def test_top_markets_response():
    r = TopMarketsResponse(
        markets=[{"country": "UK", "code": "826", "pct": 30.5, "count": 1000}],
        total=3000,
    )
    assert r.total == 3000


def test_seasonal_position_response():
    r = SeasonalPositionResponse(
        peak_month="July",
        peak_month_number=7,
        current_position="High",
        current_month="March",
        next_3_months="Moderate",
        next_months=["April", "May", "June"],
        monthly_averages={"January": 400000},
    )
    assert r.peak_month_number == 7


def test_yoy_response():
    r = YoYResponse(
        indicators={"turistas": [{"year": 2024, "month": 0, "value": 500000, "yoy_change": None}]},
        metadata={"geo": "ES709", "total_indicators": 1},
    )
    assert r.metadata.total_indicators == 1


def test_indicator_info():
    r = IndicatorInfo(
        id="turistas", source="istac",
        available_from="2010-01", available_to="2025-12",
        total_points=192,
    )
    assert r.source == "istac"
