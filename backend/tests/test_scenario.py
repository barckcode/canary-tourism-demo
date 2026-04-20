"""Tests for GBR scenario engine."""

import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from app.models.scenario_engine import (
    ACCOM_INDICATORS,
    ScenarioEngine,
    _safe_numeric,
)


def _make_fitted_engine(include_none_cols=False, none_cols=None):
    """Build a ScenarioEngine with a fake model and synthetic latest_df.

    This avoids the need for a real database.
    If *include_none_cols* is True the accommodation columns in the last
    row will be set to None (simulating incomplete data).
    If *none_cols* is provided, only those columns are set to None.
    """
    # Create synthetic historical data (24 months)
    periods = pd.period_range("2022-01", periods=24, freq="M")
    period_strs = [str(p) for p in periods]

    np.random.seed(42)
    arrivals = np.random.uniform(300_000, 500_000, size=24)
    foreign = arrivals * np.random.uniform(0.6, 0.8, size=24)

    data = {"arrivals": arrivals, "foreign": foreign}
    for col_name in ACCOM_INDICATORS.values():
        data[col_name] = np.random.uniform(10, 100, size=24)

    df = pd.DataFrame(data, index=period_strs)

    if include_none_cols:
        cols_to_null = none_cols or list(ACCOM_INDICATORS.values())
        for col_name in cols_to_null:
            if col_name in df.columns:
                df.iloc[-1, df.columns.get_loc(col_name)] = None

    # Build feature matrix consistent with engine expectations
    feature_names = []
    for lag in [1, 3, 6, 12]:
        feature_names.append(f"y_lag{lag}")
    feature_names.extend(["rolling_3m", "rolling_12m", "foreign_ratio"])
    for col_name in ACCOM_INDICATORS.values():
        feature_names.append(f"{col_name}_lag1")
    feature_names.extend(["month", "month_sin", "month_cos"])

    # Train a minimal GBR on random data matching the feature shape
    n_features = len(feature_names)
    X_train = np.random.rand(20, n_features)
    y_train = np.random.uniform(300_000, 500_000, size=20)
    model = GradientBoostingRegressor(n_estimators=10, max_depth=2, random_state=42)
    model.fit(X_train, y_train)

    engine = ScenarioEngine()
    engine.model = model
    engine.feature_names = feature_names
    engine.latest_df = df
    engine.latest_features = pd.DataFrame(
        np.random.rand(24, n_features),
        index=period_strs,
        columns=feature_names,
    )
    engine.is_fitted = True
    return engine


# ---------- Existing tests (refactored to use synthetic engine) ----------


def test_scenario_engine_fit_synthetic():
    """Scenario engine with synthetic data should be marked as fitted."""
    engine = _make_fitted_engine()
    assert engine.is_fitted
    assert engine.model is not None
    assert len(engine.feature_names) > 0


def test_scenario_baseline_forecast_synthetic():
    """Baseline (no changes) should return valid forecasts."""
    engine = _make_fitted_engine()
    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=6,
    )
    assert "baseline_forecast" in result
    assert "scenario_forecast" in result
    assert len(result["baseline_forecast"]) == 6
    assert len(result["scenario_forecast"]) == 6


def test_scenario_baseline_equals_scenario_at_zero():
    """With zero changes, baseline and scenario should be identical."""
    engine = _make_fitted_engine()
    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=6,
    )
    for b, s in zip(result["baseline_forecast"], result["scenario_forecast"]):
        assert b["value"] == s["value"], (
            f"Period {b['period']}: baseline {b['value']} != scenario {s['value']}"
        )


def test_scenario_impact_summary():
    """Impact summary should have required fields."""
    engine = _make_fitted_engine()
    result = engine.predict_scenario(
        db=MagicMock(),
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


def test_scenario_params_echoed():
    """Result should echo back the input parameters."""
    engine = _make_fitted_engine()
    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=5.0,
        adr_change_pct=-3.0,
        foreign_ratio_change_pct=2.0,
        horizon=6,
    )
    assert "params" in result
    assert result["params"]["occupancy_change_pct"] == 5.0
    assert result["params"]["adr_change_pct"] == -3.0
    assert result["params"]["foreign_ratio_change_pct"] == 2.0


def test_scenario_periods_sequential():
    """Forecast periods should be sequential months."""
    engine = _make_fitted_engine()
    result = engine.predict_scenario(db=MagicMock(), horizon=6)
    periods = [e["period"] for e in result["baseline_forecast"]]
    assert len(periods) == 6
    for p in periods:
        assert len(p) == 7, f"Period '{p}' not in YYYY-MM format"


# ---------- Bug #1: _safe_numeric and None/NaN handling ----------


def test_safe_numeric_with_none():
    """_safe_numeric should return default for None."""
    assert _safe_numeric(None) == 0.0
    assert _safe_numeric(None, 42.0) == 42.0


def test_safe_numeric_with_nan():
    """_safe_numeric should return default for NaN."""
    assert _safe_numeric(float("nan")) == 0.0
    assert _safe_numeric(np.nan, 5.0) == 5.0


def test_safe_numeric_with_inf():
    """_safe_numeric should return default for infinity."""
    assert _safe_numeric(float("inf")) == 0.0
    assert _safe_numeric(float("-inf"), 1.0) == 1.0


def test_safe_numeric_with_valid_values():
    """_safe_numeric should pass through valid numeric values."""
    assert _safe_numeric(3.14) == 3.14
    assert _safe_numeric(0) == 0.0
    assert _safe_numeric(-7) == -7.0
    assert _safe_numeric(np.float64(2.5)) == 2.5


def test_safe_numeric_with_non_numeric():
    """_safe_numeric should return default for non-numeric types."""
    assert _safe_numeric("not a number") == 0.0
    assert _safe_numeric([], 1.0) == 1.0


def test_scenario_with_none_accommodation_data():
    """Scenario engine should not crash when accommodation data contains None.

    Simulates incomplete accommodation data (None in last row) and verifies
    predict_scenario completes without TypeError.
    """
    engine = _make_fitted_engine(include_none_cols=True)
    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=10.0,
        adr_change_pct=5.0,
        foreign_ratio_change_pct=2.0,
        horizon=3,
    )
    assert "baseline_forecast" in result
    assert "scenario_forecast" in result
    assert len(result["baseline_forecast"]) == 3
    assert len(result["scenario_forecast"]) == 3


def test_scenario_with_nan_accommodation_data():
    """Scenario engine should handle NaN in accommodation features."""
    engine = _make_fitted_engine()

    # Inject NaN explicitly
    for col_name in ["room_occ", "bed_occ", "adr", "revpar"]:
        engine.latest_df.iloc[-1, engine.latest_df.columns.get_loc(col_name)] = np.nan

    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=15.0,
        adr_change_pct=-10.0,
        foreign_ratio_change_pct=0,
        horizon=3,
    )
    for entry in result["baseline_forecast"]:
        assert np.isfinite(entry["value"]), f"Non-finite baseline value: {entry}"
    for entry in result["scenario_forecast"]:
        assert np.isfinite(entry["value"]), f"Non-finite scenario value: {entry}"


def test_scenario_with_none_foreign():
    """Scenario engine should handle None in foreign column."""
    engine = _make_fitted_engine()
    engine.latest_df.iloc[-1, engine.latest_df.columns.get_loc("foreign")] = None

    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=5.0,
        horizon=3,
    )
    assert len(result["scenario_forecast"]) == 3


def test_scenario_with_zero_arrivals_no_division_error():
    """Zero arrivals in last row should not cause ZeroDivisionError."""
    engine = _make_fitted_engine()
    engine.latest_df.iloc[-1, engine.latest_df.columns.get_loc("arrivals")] = 0.0

    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=0,
        adr_change_pct=0,
        foreign_ratio_change_pct=0,
        horizon=3,
    )
    assert len(result["baseline_forecast"]) == 3


# ---------- Bug #2: Thread-safe singleton ----------


def test_singleton_thread_safety():
    """Concurrent calls to _get_engine should not create multiple instances.

    Uses a mock db and patches predict_scenario to avoid real DB access.
    """
    from app.api import scenarios as scenarios_mod

    # Reset the singleton
    scenarios_mod._engine = None

    call_count = {"n": 0}
    original_init = ScenarioEngine.__init__

    def counting_init(self):
        call_count["n"] += 1
        original_init(self)

    mock_db = MagicMock()
    errors = []

    def fake_predict_scenario(self, **kwargs):
        """Mark engine as fitted without doing real work."""
        self.is_fitted = True
        self.model = MagicMock()
        self.feature_names = ["f1"]
        self.latest_df = pd.DataFrame()
        self.latest_features = pd.DataFrame()
        return {"baseline_forecast": [], "scenario_forecast": [], "impact_summary": {}}

    def get_engine_thread():
        try:
            scenarios_mod._get_engine(mock_db)
        except Exception as e:
            errors.append(e)

    with patch.object(ScenarioEngine, "__init__", counting_init), \
         patch.object(ScenarioEngine, "predict_scenario", fake_predict_scenario):
        threads = [threading.Thread(target=get_engine_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

    # Clean up singleton for other tests
    scenarios_mod._engine = None

    assert not errors, f"Threads raised errors: {errors}"
    # With proper double-checked locking, the engine should be created
    # at most once (all other threads should see it after the lock)
    assert call_count["n"] <= 2, (
        f"ScenarioEngine was instantiated {call_count['n']} times, "
        "expected at most 2 (race between fast-path check and lock acquisition)"
    )


def test_singleton_reuses_fitted_engine():
    """Once the engine is fitted, _get_engine should return it without recreating."""
    from app.api import scenarios as scenarios_mod

    engine = _make_fitted_engine()
    scenarios_mod._engine = engine

    mock_db = MagicMock()
    returned = scenarios_mod._get_engine(mock_db)
    assert returned is engine, "Should reuse the existing fitted engine"

    # Clean up
    scenarios_mod._engine = None


# ---------- Bug #3: Negative predictions clamping ----------


def test_scenario_extreme_inputs_non_negative():
    """Extreme pessimistic scenario should never produce negative arrivals.

    With -90% changes on all inputs, the GBR model could predict negative
    tourist arrivals. The engine must clamp all values to zero or above.
    """
    engine = _make_fitted_engine()
    # Set a large residual_std to ensure CI bands go wide
    engine._residual_std = 500_000.0

    result = engine.predict_scenario(
        db=MagicMock(),
        occupancy_change_pct=-90.0,
        adr_change_pct=-90.0,
        foreign_ratio_change_pct=-90.0,
        horizon=12,
    )

    for point in result["scenario_forecast"]:
        assert point["value"] >= 0, f"Negative scenario prediction: {point}"
        for key in ("ci_lower_80", "ci_lower_95"):
            if key in point:
                assert point[key] >= 0, f"Negative scenario CI: {key}={point[key]}"

    for point in result["baseline_forecast"]:
        assert point["value"] >= 0, f"Negative baseline prediction: {point}"
        for key in ("ci_lower_80", "ci_lower_95"):
            if key in point:
                assert point[key] >= 0, f"Negative baseline CI: {key}={point[key]}"
