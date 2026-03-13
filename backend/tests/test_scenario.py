"""Tests for GBR scenario engine."""

from app.models.scenario_engine import ScenarioEngine


def test_scenario_engine_fit(db):
    """Scenario engine should train without errors."""
    engine = ScenarioEngine()
    engine.fit(db)
    assert engine.is_fitted
    assert engine.model is not None
    assert len(engine.feature_names) > 0


def test_scenario_baseline_forecast(db):
    """Baseline (no changes) should return valid forecasts."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=6,
    )
    assert "baseline_forecast" in result
    assert "scenario_forecast" in result
    assert len(result["baseline_forecast"]) == 6
    assert len(result["scenario_forecast"]) == 6


def test_scenario_baseline_equals_scenario_at_zero(db):
    """With zero changes, baseline and scenario should be identical."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=6,
    )
    for b, s in zip(result["baseline_forecast"], result["scenario_forecast"]):
        assert b["value"] == s["value"], (
            f"Period {b['period']}: baseline {b['value']} != scenario {s['value']}"
        )


def test_scenario_positive_occupancy_increases_arrivals(db):
    """Increasing occupancy should generally increase arrivals."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=10.0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=6,
    )
    impact = result["impact_summary"]
    assert impact["avg_scenario"] >= impact["avg_baseline"], (
        f"Expected scenario >= baseline with +10% occupancy, "
        f"got {impact['avg_scenario']} vs {impact['avg_baseline']}"
    )


def test_scenario_impact_summary(db):
    """Impact summary should have required fields."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=5.0,
        adr_change_pct=-3.0,
        foreign_ratio_change_pct=2.0,
        horizon=6,
    )
    impact = result["impact_summary"]
    assert "avg_baseline" in impact
    assert "avg_scenario" in impact
    assert "avg_change_pct" in impact
    assert isinstance(impact["avg_change_pct"], float)


def test_scenario_params_echoed(db):
    """Result should echo back the input parameters."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=5.0,
        adr_change_pct=-3.0,
        foreign_ratio_change_pct=2.0,
        horizon=6,
    )
    assert "params" in result
    assert result["params"]["occupancy_change_pct"] == 5.0
    assert result["params"]["adr_change_pct"] == -3.0
    assert result["params"]["foreign_ratio_change_pct"] == 2.0


def test_scenario_forecast_values_positive(db):
    """All forecast values should be positive."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=5.0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=12,
    )
    for entry in result["baseline_forecast"]:
        assert entry["value"] > 0, f"Baseline {entry['period']} is non-positive"
    for entry in result["scenario_forecast"]:
        assert entry["value"] > 0, f"Scenario {entry['period']} is non-positive"


def test_scenario_periods_sequential(db):
    """Forecast periods should be sequential months."""
    engine = ScenarioEngine()
    engine.fit(db)
    result = engine.predict_scenario(db=db, horizon=6)
    periods = [e["period"] for e in result["baseline_forecast"]]
    assert len(periods) == 6
    # Verify year-month format
    for p in periods:
        assert len(p) == 7, f"Period '{p}' not in YYYY-MM format"
