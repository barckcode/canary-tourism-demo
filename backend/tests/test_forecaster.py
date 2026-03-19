"""Tests for SARIMA + Holt-Winters + ensemble forecaster."""

import re

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.models.forecaster import Forecaster


def _load_series(db) -> pd.Series:
    """Helper to load arrivals series from DB."""
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
            ORDER BY period
        """)
    ).fetchall()
    monthly = [(r.period, r.value) for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)]
    periods = pd.PeriodIndex([p for p, _ in monthly], freq="M")
    values = np.array([v for _, v in monthly], dtype=float)
    return pd.Series(values, index=periods, name="turistas")


def test_forecaster_fit(db):
    """Forecaster should fit without errors."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    assert f.is_fitted
    assert f.sarima_result is not None
    assert f.hw_result is not None


def test_forecaster_predict_ensemble(db):
    """Ensemble prediction should return correct structure."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict(horizon=12)

    assert len(result.periods) == 12
    assert len(result.values) == 12
    assert len(result.ci_lower_80) == 12
    assert len(result.ci_upper_80) == 12
    assert len(result.ci_lower_95) == 12
    assert len(result.ci_upper_95) == 12


def test_forecaster_values_reasonable(db):
    """Forecast values should be in a reasonable range for Tenerife tourism."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict(horizon=12)

    for val in result.values:
        assert 200_000 < val < 1_500_000, (
            f"Forecast {val} outside reasonable range"
        )


def test_forecaster_ci_ordering(db):
    """Confidence intervals should be properly ordered: 95_lo < 80_lo < value < 80_hi < 95_hi."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict(horizon=12)

    for i in range(12):
        assert result.ci_lower_95[i] <= result.ci_lower_80[i], (
            f"Period {i}: 95% lower > 80% lower"
        )
        assert result.ci_lower_80[i] <= result.values[i], (
            f"Period {i}: 80% lower > value"
        )
        assert result.values[i] <= result.ci_upper_80[i], (
            f"Period {i}: value > 80% upper"
        )
        assert result.ci_upper_80[i] <= result.ci_upper_95[i], (
            f"Period {i}: 80% upper > 95% upper"
        )


def test_forecaster_periods_sequential(db):
    """Forecast periods should be sequential months after the last data point."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict(horizon=6)

    last_data = series.index[-1]
    first_forecast = pd.Period(result.periods[0], freq="M")
    assert first_forecast == last_data + 1, (
        f"First forecast {first_forecast} should be one month after {last_data}"
    )


def test_sarima_standalone(db):
    """SARIMA-only forecast should work independently."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_sarima(horizon=6)
    assert len(result.values) == 6
    assert all(v > 0 for v in result.values)


def test_hw_standalone(db):
    """Holt-Winters forecast should work independently."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_hw(horizon=6)
    assert len(result.values) == 6
    assert all(v > 0 for v in result.values)


def test_naive_standalone(db):
    """Seasonal Naive should repeat last year's values."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_naive(horizon=12)
    last_12 = series.values[-12:]
    np.testing.assert_array_almost_equal(result.values, last_12)


def test_evaluate_returns_metrics_for_all_models(db):
    """Evaluate should return RMSE, MAE, MAPE for all four model types."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    metrics = f.evaluate(test_size=12)

    assert len(metrics) == 4
    for name in ["sarima", "holt_winters", "seasonal_naive", "ensemble"]:
        assert name in metrics, f"Missing metrics for {name}"
        m = metrics[name]
        assert m.rmse > 0, f"{name} RMSE should be positive"
        assert m.mae > 0, f"{name} MAE should be positive"
        assert 0 < m.mape < 100, f"{name} MAPE {m.mape}% outside 0-100 range"


def test_hw_ci_ordering(db):
    """Holt-Winters CIs should be properly ordered: 95_lo < 80_lo < value < 80_hi < 95_hi."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_hw(horizon=12)

    for i in range(12):
        assert result.ci_lower_95[i] <= result.ci_lower_80[i], (
            f"HW period {i}: 95% lower > 80% lower"
        )
        assert result.ci_lower_80[i] <= result.values[i], (
            f"HW period {i}: 80% lower > value"
        )
        assert result.values[i] <= result.ci_upper_80[i], (
            f"HW period {i}: value > 80% upper"
        )
        assert result.ci_upper_80[i] <= result.ci_upper_95[i], (
            f"HW period {i}: 80% upper > 95% upper"
        )


def test_hw_ci_expands_with_horizon(db):
    """Holt-Winters CI width should increase with forecast horizon."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_hw(horizon=12)

    widths_95 = result.ci_upper_95 - result.ci_lower_95
    # Each subsequent width should be >= the previous one
    for i in range(1, 12):
        assert widths_95[i] >= widths_95[i - 1], (
            f"HW CI width at step {i} ({widths_95[i]}) < step {i-1} ({widths_95[i-1]})"
        )


def test_hw_ci_non_negative(db):
    """Holt-Winters CI lower bounds should never be negative."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_hw(horizon=24)

    assert np.all(result.ci_lower_80 >= 0), "HW 80% CI lower bound went negative"
    assert np.all(result.ci_lower_95 >= 0), "HW 95% CI lower bound went negative"


def test_naive_ci_ordering(db):
    """Seasonal Naive CIs should be properly ordered."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_naive(horizon=12)

    for i in range(12):
        assert result.ci_lower_95[i] <= result.ci_lower_80[i], (
            f"Naive period {i}: 95% lower > 80% lower"
        )
        assert result.ci_lower_80[i] <= result.values[i], (
            f"Naive period {i}: 80% lower > value"
        )
        assert result.values[i] <= result.ci_upper_80[i], (
            f"Naive period {i}: value > 80% upper"
        )
        assert result.ci_upper_80[i] <= result.ci_upper_95[i], (
            f"Naive period {i}: 80% upper > 95% upper"
        )


def test_naive_ci_expands_with_horizon(db):
    """Seasonal Naive CI width should increase with forecast horizon."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_naive(horizon=12)

    widths_95 = result.ci_upper_95 - result.ci_lower_95
    for i in range(1, 12):
        assert widths_95[i] >= widths_95[i - 1], (
            f"Naive CI width at step {i} ({widths_95[i]}) < step {i-1} ({widths_95[i-1]})"
        )


def test_naive_ci_non_negative(db):
    """Seasonal Naive CI lower bounds should never be negative."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_naive(horizon=24)

    assert np.all(result.ci_lower_80 >= 0), "Naive 80% CI lower bound went negative"
    assert np.all(result.ci_lower_95 >= 0), "Naive 95% CI lower bound went negative"


def test_hw_ci_not_hardcoded(db):
    """HW CIs should NOT be simple percentage multipliers of mean."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_hw(horizon=12)

    # If CIs were hardcoded as mean*0.9 / mean*1.1, the ratio would be constant
    ratios_lower = result.ci_lower_80 / result.values
    ratios_upper = result.ci_upper_80 / result.values
    # With proper expanding CIs, ratios should vary across horizon steps
    assert not np.allclose(ratios_lower, ratios_lower[0], atol=1e-6), (
        "HW lower CI ratios are constant — CIs may still be hardcoded"
    )
    assert not np.allclose(ratios_upper, ratios_upper[0], atol=1e-6), (
        "HW upper CI ratios are constant — CIs may still be hardcoded"
    )


def test_naive_ci_not_hardcoded(db):
    """Naive CIs should NOT be simple percentage multipliers of mean."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    result = f.predict_naive(horizon=12)

    ratios_lower = result.ci_lower_80 / result.values
    ratios_upper = result.ci_upper_80 / result.values
    assert not np.allclose(ratios_lower, ratios_lower[0], atol=1e-6), (
        "Naive lower CI ratios are constant — CIs may still be hardcoded"
    )
    assert not np.allclose(ratios_upper, ratios_upper[0], atol=1e-6), (
        "Naive upper CI ratios are constant — CIs may still be hardcoded"
    )


def test_evaluate_ensemble_best_or_competitive(db):
    """Ensemble MAPE should be reasonable (< 50%) and not drastically worse than best model."""
    series = _load_series(db)
    f = Forecaster()
    f.fit(series, exclude_covid=True)
    metrics = f.evaluate(test_size=12)

    individual_mapes = [
        metrics[k].mape for k in ["sarima", "holt_winters", "seasonal_naive"]
    ]
    best_individual = min(individual_mapes)
    ensemble_mape = metrics["ensemble"].mape
    # Ensemble should have a reasonable MAPE under 50%
    assert ensemble_mape < 50, f"Ensemble MAPE {ensemble_mape}% is too high"
    # Ensemble should not be drastically worse than the best individual model
    # (allow up to 10x for synthetic data where individual models can be near-perfect)
    assert ensemble_mape <= max(best_individual * 10.0, 15.0), (
        f"Ensemble MAPE {ensemble_mape} much worse than best individual {best_individual}"
    )
