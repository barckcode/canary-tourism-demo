"""SARIMA + Holt-Winters ensemble forecaster.

Implements:
- SARIMA(2,0,1)(2,0,0,12) as primary forecaster
- Holt-Winters exponential smoothing with multiplicative seasonality
- Seasonal Naive as baseline
- Weighted ensemble combining all three
"""

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

logger = logging.getLogger(__name__)

# COVID exclusion range indices (relative to 2010-01 start)
COVID_START = "2020-03"
COVID_END = "2021-06"

# Ensemble weights: SARIMA(0.5), HW(0.3), Seasonal Naive(0.2)
WEIGHTS_MEDIUM = {"sarima": 0.5, "hw": 0.3, "naive": 0.2}
WEIGHTS_SHORT = {"sarima": 0.7, "hw": 0.2, "naive": 0.1}


@dataclass
class ForecastResult:
    periods: list[str]
    values: np.ndarray
    ci_lower_80: np.ndarray
    ci_upper_80: np.ndarray
    ci_lower_95: np.ndarray
    ci_upper_95: np.ndarray


class Forecaster:
    """Tourism demand forecaster using SARIMA + HW + Seasonal Naive ensemble."""

    def __init__(self):
        self.sarima_model = None
        self.sarima_result = None
        self.hw_model = None
        self.hw_result = None
        self.series = None
        self.index = None
        self.is_fitted = False

    def fit(self, series: pd.Series, exclude_covid: bool = True):
        """Train all models on the given time series.

        Args:
            series: Monthly tourist arrivals with PeriodIndex.
            exclude_covid: Whether to exclude COVID period.
        """
        self.series = series.copy()
        self.index = series.index

        train = series.copy()
        if exclude_covid:
            mask = ~((train.index >= pd.Period(COVID_START, freq="M"))
                     & (train.index <= pd.Period(COVID_END, freq="M")))
            # Rebuild continuous index and interpolate COVID gap
            full_idx = pd.period_range(
                train.index[0], train.index[-1], freq="M"
            )
            train = train.reindex(full_idx)
            train = train.interpolate(method="linear")
            logger.info(
                "Excluded COVID period: %d months interpolated.",
                (~mask).sum(),
            )

        # 1) SARIMA(2,0,1)(2,0,0,12)
        logger.info("Fitting SARIMA(2,0,1)(2,0,0,12)...")
        self.sarima_model = SARIMAX(
            train,
            order=(2, 0, 1),
            seasonal_order=(2, 0, 0, 12),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        self.sarima_result = self.sarima_model.fit(disp=False, maxiter=200)
        logger.info("SARIMA AIC: %.2f", self.sarima_result.aic)

        # 2) Holt-Winters (multiplicative seasonality)
        logger.info("Fitting Holt-Winters...")
        self.hw_model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal="mul",
            seasonal_periods=12,
            initialization_method="estimated",
        )
        self.hw_result = self.hw_model.fit(optimized=True)

        self.is_fitted = True
        logger.info("All models fitted successfully.")

    def _seasonal_naive(self, horizon: int) -> np.ndarray:
        """Forecast using same month last year."""
        last_12 = self.series.values[-12:]
        repeats = (horizon // 12) + 1
        naive = np.tile(last_12, repeats)[:horizon]
        return naive

    def predict(self, horizon: int = 12) -> ForecastResult:
        """Generate ensemble forecast with confidence intervals."""
        if not self.is_fitted:
            raise RuntimeError("Models not fitted. Call fit() first.")

        last_period = self.series.index[-1]
        future_periods = pd.period_range(
            last_period + 1, periods=horizon, freq="M"
        )

        # SARIMA forecast with confidence intervals
        sarima_fc = self.sarima_result.get_forecast(steps=horizon)
        sarima_mean = sarima_fc.predicted_mean.values
        sarima_ci_80 = sarima_fc.conf_int(alpha=0.20).values
        sarima_ci_95 = sarima_fc.conf_int(alpha=0.05).values

        # Holt-Winters forecast
        hw_mean = self.hw_result.forecast(horizon).values

        # Seasonal Naive
        naive_mean = self._seasonal_naive(horizon)

        # Ensemble (use short-term weights for h<=3, medium for h>3)
        ensemble = np.zeros(horizon)
        for h in range(horizon):
            w = WEIGHTS_SHORT if h < 3 else WEIGHTS_MEDIUM
            ensemble[h] = (
                w["sarima"] * sarima_mean[h]
                + w["hw"] * hw_mean[h]
                + w["naive"] * naive_mean[h]
            )

        # Use SARIMA CIs scaled by ensemble/sarima ratio for CI bands
        ratio = np.where(sarima_mean != 0, ensemble / sarima_mean, 1.0)
        ci_lower_80 = sarima_ci_80[:, 0] * ratio
        ci_upper_80 = sarima_ci_80[:, 1] * ratio
        ci_lower_95 = sarima_ci_95[:, 0] * ratio
        ci_upper_95 = sarima_ci_95[:, 1] * ratio

        return ForecastResult(
            periods=[str(p) for p in future_periods],
            values=ensemble,
            ci_lower_80=ci_lower_80,
            ci_upper_80=ci_upper_80,
            ci_lower_95=ci_lower_95,
            ci_upper_95=ci_upper_95,
        )

    def predict_sarima(self, horizon: int = 12) -> ForecastResult:
        """SARIMA-only forecast."""
        if not self.sarima_result:
            raise RuntimeError("SARIMA not fitted.")

        last_period = self.series.index[-1]
        future_periods = pd.period_range(
            last_period + 1, periods=horizon, freq="M"
        )

        fc = self.sarima_result.get_forecast(steps=horizon)
        mean = fc.predicted_mean.values
        ci_80 = fc.conf_int(alpha=0.20).values
        ci_95 = fc.conf_int(alpha=0.05).values

        return ForecastResult(
            periods=[str(p) for p in future_periods],
            values=mean,
            ci_lower_80=ci_80[:, 0],
            ci_upper_80=ci_80[:, 1],
            ci_lower_95=ci_95[:, 0],
            ci_upper_95=ci_95[:, 1],
        )

    def predict_hw(self, horizon: int = 12) -> ForecastResult:
        """Holt-Winters-only forecast (no CI bands)."""
        if not self.hw_result:
            raise RuntimeError("Holt-Winters not fitted.")

        last_period = self.series.index[-1]
        future_periods = pd.period_range(
            last_period + 1, periods=horizon, freq="M"
        )
        mean = self.hw_result.forecast(horizon).values

        return ForecastResult(
            periods=[str(p) for p in future_periods],
            values=mean,
            ci_lower_80=mean * 0.9,
            ci_upper_80=mean * 1.1,
            ci_lower_95=mean * 0.85,
            ci_upper_95=mean * 1.15,
        )

    def predict_naive(self, horizon: int = 12) -> ForecastResult:
        """Seasonal Naive forecast (no CI bands)."""
        last_period = self.series.index[-1]
        future_periods = pd.period_range(
            last_period + 1, periods=horizon, freq="M"
        )
        mean = self._seasonal_naive(horizon)

        return ForecastResult(
            periods=[str(p) for p in future_periods],
            values=mean,
            ci_lower_80=mean * 0.9,
            ci_upper_80=mean * 1.1,
            ci_lower_95=mean * 0.85,
            ci_upper_95=mean * 1.15,
        )
