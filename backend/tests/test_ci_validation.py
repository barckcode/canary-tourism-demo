"""Tests for confidence interval bounds validation in ensemble forecaster.

Verifies that CI bounds are never inverted (lower > upper) and never negative,
even when the SARIMA-to-ensemble ratio scaling could theoretically flip them.
"""

import numpy as np
import pandas as pd
import pytest

from app.models.forecaster import Forecaster


def _make_seasonal_series(n_years: int = 8) -> pd.Series:
    """Create a synthetic monthly tourism series with clear seasonality."""
    rng = np.random.default_rng(42)
    periods = n_years * 12
    idx = pd.period_range("2016-01", periods=periods, freq="M")

    trend = np.linspace(100_000, 150_000, periods)
    seasonal = 30_000 * np.sin(2 * np.pi * np.arange(periods) / 12)
    noise = rng.normal(0, 5_000, periods)
    values = trend + seasonal + noise

    return pd.Series(values, index=idx, name="tourists")


@pytest.fixture
def fitted_forecaster() -> Forecaster:
    """Return a Forecaster fitted on synthetic data."""
    series = _make_seasonal_series()
    fc = Forecaster()
    fc.fit(series, exclude_covid=False)
    return fc


class TestCIBoundsValidation:
    """Ensemble forecast CI bounds must be well-ordered and non-negative."""

    def test_ci_lower_le_upper_80(self, fitted_forecaster: Forecaster):
        result = fitted_forecaster.predict(horizon=12)
        assert np.all(result.ci_lower_80 <= result.ci_upper_80), (
            "ci_lower_80 must be <= ci_upper_80 for all forecast steps"
        )

    def test_ci_lower_le_upper_95(self, fitted_forecaster: Forecaster):
        result = fitted_forecaster.predict(horizon=12)
        assert np.all(result.ci_lower_95 <= result.ci_upper_95), (
            "ci_lower_95 must be <= ci_upper_95 for all forecast steps"
        )

    def test_ci_values_non_negative(self, fitted_forecaster: Forecaster):
        result = fitted_forecaster.predict(horizon=12)
        assert np.all(result.ci_lower_80 >= 0), "ci_lower_80 must be >= 0"
        assert np.all(result.ci_lower_95 >= 0), "ci_lower_95 must be >= 0"
        assert np.all(result.ci_upper_80 >= 0), "ci_upper_80 must be >= 0"
        assert np.all(result.ci_upper_95 >= 0), "ci_upper_95 must be >= 0"

    def test_95_ci_wider_than_80(self, fitted_forecaster: Forecaster):
        """The 95% interval should be at least as wide as the 80% interval."""
        result = fitted_forecaster.predict(horizon=12)
        assert np.all(result.ci_lower_95 <= result.ci_lower_80), (
            "95% lower bound should be <= 80% lower bound"
        )
        assert np.all(result.ci_upper_95 >= result.ci_upper_80), (
            "95% upper bound should be >= 80% upper bound"
        )

    def test_longer_horizon(self, fitted_forecaster: Forecaster):
        """Validation holds for longer forecast horizons too."""
        result = fitted_forecaster.predict(horizon=24)
        assert np.all(result.ci_lower_80 <= result.ci_upper_80)
        assert np.all(result.ci_lower_95 <= result.ci_upper_95)
        assert np.all(result.ci_lower_80 >= 0)
        assert np.all(result.ci_lower_95 >= 0)
