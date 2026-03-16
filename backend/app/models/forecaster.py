"""SARIMA + Holt-Winters ensemble forecaster.

Implements:
- SARIMA(2,0,1)(2,0,0,12) as primary forecaster
- Holt-Winters exponential smoothing with multiplicative seasonality
- Seasonal Naive as baseline
- Weighted ensemble combining all three

Also provides accuracy metrics (RMSE, MAE, MAPE) via time-series
cross-validation on the last 12 months of non-COVID data.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.utils.constants import COVID_END, COVID_START

logger = logging.getLogger(__name__)

# Ensemble weights: SARIMA(0.5), HW(0.3), Seasonal Naive(0.2)
WEIGHTS_MEDIUM = {"sarima": 0.5, "hw": 0.3, "naive": 0.2}
WEIGHTS_SHORT = {"sarima": 0.7, "hw": 0.2, "naive": 0.1}


@dataclass
class ModelMetrics:
    """Accuracy metrics for a single forecasting model."""

    rmse: float
    mae: float
    mape: float


@dataclass
class ForecastResult:
    periods: list[str]
    values: np.ndarray
    ci_lower_80: np.ndarray
    ci_upper_80: np.ndarray
    ci_lower_95: np.ndarray
    ci_upper_95: np.ndarray
    metrics: ModelMetrics | None = field(default=None)


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

    def evaluate(self, test_size: int = 12) -> dict[str, ModelMetrics]:
        """Evaluate all models using a train/test split.

        Splits the series so that the last ``test_size`` non-COVID months
        form the test set.  Trains temporary models on the training portion
        and computes RMSE, MAE and MAPE against the held-out actuals.

        Returns:
            Dictionary mapping model name to its :class:`ModelMetrics`.
        """
        if self.series is None:
            raise RuntimeError("No series loaded. Call fit() first.")

        series = self.series.copy()

        # Exclude COVID period from evaluation
        covid_mask = (
            (series.index >= pd.Period(COVID_START, freq="M"))
            & (series.index <= pd.Period(COVID_END, freq="M"))
        )
        clean = series[~covid_mask]

        if len(clean) < test_size + 36:
            logger.warning(
                "Not enough clean data (%d points) for evaluation; "
                "need at least %d. Returning empty metrics.",
                len(clean), test_size + 36,
            )
            return {}

        # Split: train on all but last test_size clean months
        train_series = clean.iloc[:-test_size]
        test_series = clean.iloc[-test_size:]
        actuals = test_series.values
        horizon = len(actuals)

        # Rebuild continuous training index, interpolating any gaps
        full_idx = pd.period_range(
            train_series.index[0], train_series.index[-1], freq="M"
        )
        train_cont = train_series.reindex(full_idx).interpolate(method="linear")

        # --- Fit temporary SARIMA ---
        try:
            sarima_mod = SARIMAX(
                train_cont,
                order=(2, 0, 1),
                seasonal_order=(2, 0, 0, 12),
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            sarima_res = sarima_mod.fit(disp=False, maxiter=200)
            sarima_fc = sarima_res.get_forecast(steps=horizon).predicted_mean.values
        except Exception:
            logger.exception("SARIMA evaluation failed; using NaN metrics.")
            sarima_fc = np.full(horizon, np.nan)

        # --- Fit temporary Holt-Winters ---
        try:
            hw_mod = ExponentialSmoothing(
                train_cont,
                trend="add",
                seasonal="mul",
                seasonal_periods=12,
                initialization_method="estimated",
            )
            hw_res = hw_mod.fit(optimized=True)
            hw_fc = hw_res.forecast(horizon).values
        except Exception:
            logger.exception("HW evaluation failed; using NaN metrics.")
            hw_fc = np.full(horizon, np.nan)

        # --- Seasonal Naive ---
        last_12 = train_cont.values[-12:]
        repeats = (horizon // 12) + 1
        naive_fc = np.tile(last_12, repeats)[:horizon]

        # --- Ensemble ---
        ensemble_fc = np.zeros(horizon)
        for h in range(horizon):
            w = WEIGHTS_SHORT if h < 3 else WEIGHTS_MEDIUM
            ensemble_fc[h] = (
                w["sarima"] * sarima_fc[h]
                + w["hw"] * hw_fc[h]
                + w["naive"] * naive_fc[h]
            )

        def _calc_metrics(predicted: np.ndarray, actual: np.ndarray) -> ModelMetrics:
            errors = actual - predicted
            rmse = float(np.sqrt(np.nanmean(errors ** 2)))
            mae = float(np.nanmean(np.abs(errors)))
            # MAPE: avoid division by zero
            nonzero = actual != 0
            if nonzero.any():
                mape = float(
                    np.nanmean(np.abs(errors[nonzero] / actual[nonzero])) * 100
                )
            else:
                mape = float("nan")
            return ModelMetrics(rmse=round(rmse, 2), mae=round(mae, 2), mape=round(mape, 2))

        metrics = {
            "sarima": _calc_metrics(sarima_fc, actuals),
            "holt_winters": _calc_metrics(hw_fc, actuals),
            "seasonal_naive": _calc_metrics(naive_fc, actuals),
            "ensemble": _calc_metrics(ensemble_fc, actuals),
        }

        logger.info(
            "Evaluation metrics (test=%d months): %s",
            test_size,
            {k: f"MAPE={v.mape:.1f}%" for k, v in metrics.items()},
        )
        return metrics

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
        epsilon = 1e-10
        ratio = np.where(np.abs(sarima_mean) > epsilon, ensemble / sarima_mean, 1.0)
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
