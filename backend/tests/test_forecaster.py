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
