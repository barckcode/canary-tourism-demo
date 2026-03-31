"""GBR scenario engine for what-if analysis.

Uses Gradient Boosting Regressor trained on multivariate features
(lagged arrivals, accommodation metrics) to enable what-if scenario
exploration with user-adjustable inputs.
"""

import logging
import math
import re
import threading

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.utils.constants import COVID_END, COVID_START

logger = logging.getLogger(__name__)


def _safe_numeric(value: object, default: float = 0.0) -> float:
    """Return a finite float from *value*, falling back to *default*.

    Handles None, NaN, and non-numeric types gracefully so that
    downstream arithmetic never crashes on missing data.
    """
    if value is None:
        return default
    try:
        fval = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(fval) or math.isinf(fval):
        return default
    return fval

# Accommodation indicators used as features
ACCOM_INDICATORS = {
    "alojatur_habitaciones_ocupacion": "room_occ",
    "alojatur_plazas_ocupacion": "bed_occ",
    "alojatur_tarifa_adr": "adr",
    "alojatur_ingresos": "revpar",
    "alojatur_pernoctaciones": "overnight_stays",
}


def _load_feature_data(db: Session) -> pd.DataFrame:
    """Load arrivals + accommodation metrics aligned by period."""
    from app.utils.queries import load_arrivals_series

    # Arrivals — reuse the shared query helper
    arrivals = load_arrivals_series(db)
    df = pd.DataFrame({"arrivals": arrivals.values}, index=[str(p) for p in arrivals.index])

    # Foreign tourists
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator='turistas_extranjeros' AND geo_code='ES709' AND measure='ABSOLUTE'
            ORDER BY period
        """)
    ).fetchall()
    foreign = {r.period: r.value for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)}
    df["foreign"] = df.index.map(lambda p: foreign.get(p))

    # Accommodation features
    for indicator, col_name in ACCOM_INDICATORS.items():
        rows = db.execute(
            text("""
                SELECT period, value FROM time_series
                WHERE indicator=:ind AND geo_code='ES709' AND measure='ABSOLUTE'
                ORDER BY period
            """),
            {"ind": indicator},
        ).fetchall()
        vals = {r.period: r.value for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)}
        df[col_name] = df.index.map(lambda p, v=vals: v.get(p))

    return df


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create feature matrix with lags and rolling stats."""
    features = pd.DataFrame(index=df.index)

    # Lagged arrivals
    for lag in [1, 3, 6, 12]:
        features[f"y_lag{lag}"] = df["arrivals"].shift(lag)

    # Rolling statistics
    features["rolling_3m"] = df["arrivals"].rolling(3).mean()
    features["rolling_12m"] = df["arrivals"].rolling(12).mean()

    # Foreign ratio (safe division to avoid division by zero)
    features["foreign_ratio"] = np.where(df["arrivals"] != 0, df["foreign"] / df["arrivals"], 0.5)

    # Lagged accommodation metrics
    for col_name in ACCOM_INDICATORS.values():
        features[f"{col_name}_lag1"] = df[col_name].shift(1)

    # Month encoding
    periods = pd.PeriodIndex(df.index, freq="M")
    features["month"] = periods.month
    features["month_sin"] = np.sin(2 * np.pi * periods.month / 12)
    features["month_cos"] = np.cos(2 * np.pi * periods.month / 12)

    return features


class ScenarioEngine:
    """What-if scenario engine using Gradient Boosting Regressor."""

    def __init__(self):
        self.model = None
        self.is_fitted = False
        self.feature_names = []
        self.latest_features = None
        self.latest_df = None
        self._residual_std: float = 0.0
        self._predict_lock = threading.Lock()

    def fit(self, db: Session):
        """Train GBR model on historical data."""
        logger.info("Loading feature data for GBR...")
        df = _load_feature_data(db)
        features = _build_features(df)

        # Align features with target
        target = df["arrivals"]
        combined = features.join(target).dropna()

        # Exclude COVID period
        mask = ~((combined.index >= COVID_START) & (combined.index <= COVID_END))
        combined = combined[mask]

        X = combined.drop("arrivals", axis=1)
        y = combined["arrivals"]

        self.feature_names = X.columns.tolist()

        logger.info("Training GBR on %d samples, %d features.", len(X), len(self.feature_names))
        self.model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )
        self.model.fit(X, y)

        # Compute residual standard error for confidence intervals
        y_pred_train = self.model.predict(X)
        residuals = y.values - y_pred_train
        self._residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0

        # Store latest state for scenario generation
        self.latest_df = df
        self.latest_features = features
        self.is_fitted = True

        # Log feature importances
        importances = sorted(
            zip(self.feature_names, self.model.feature_importances_),
            key=lambda x: x[1],
            reverse=True,
        )
        logger.info("Top 5 features: %s",
                     [(n, f"{v:.3f}") for n, v in importances[:5]])

        return self

    def _ensure_fitted(self, db: Session) -> None:
        """Load model from disk or train from scratch if not already fitted."""
        if self.is_fitted:
            return
        model_path = settings.models_dir / "scenario_engine.pkl"
        if model_path.exists():
            saved = joblib.load(model_path)
            self.model = saved.model
            self.feature_names = saved.feature_names
            self.latest_df = saved.latest_df
            self.latest_features = saved.latest_features
            self._residual_std = getattr(saved, '_residual_std', 0.0)
            self.is_fitted = True
        else:
            self.fit(db)

    def _build_period_features(
        self, ext_df: pd.DataFrame, period: pd.Period
    ) -> dict:
        """Build a single-row feature dict for a future period.

        Uses the extended DataFrame (which grows each iteration) to compute
        lagged arrivals, rolling means, foreign ratio, accommodation lags,
        and month encodings.
        """
        feat: dict = {}
        arrivals_series = pd.Series(
            {p: ext_df.loc[p, "arrivals"] for p in ext_df.index},
        )

        for lag in [1, 3, 6, 12]:
            idx = len(arrivals_series) - lag
            feat[f"y_lag{lag}"] = arrivals_series.iloc[idx] if idx >= 0 else np.nan

        feat["rolling_3m"] = arrivals_series.iloc[-3:].mean()
        feat["rolling_12m"] = arrivals_series.iloc[-12:].mean()

        last_arrivals = _safe_numeric(ext_df["arrivals"].iloc[-1])
        last_foreign = _safe_numeric(ext_df["foreign"].iloc[-1])
        feat["foreign_ratio"] = (
            last_foreign / last_arrivals if last_arrivals != 0 else 0.5
        )

        for col_name in ACCOM_INDICATORS.values():
            feat[f"{col_name}_lag1"] = _safe_numeric(ext_df[col_name].iloc[-1])

        feat["month"] = period.month
        feat["month_sin"] = np.sin(2 * np.pi * period.month / 12)
        feat["month_cos"] = np.cos(2 * np.pi * period.month / 12)

        return feat

    @staticmethod
    def _apply_scenario(
        feat: dict,
        occupancy_change_pct: float,
        adr_change_pct: float,
        foreign_ratio_change_pct: float,
    ) -> dict:
        """Return a copy of *feat* with what-if modifications applied."""
        feat_sc = feat.copy()
        if occupancy_change_pct:
            feat_sc["room_occ_lag1"] = _safe_numeric(feat_sc["room_occ_lag1"]) * (1 + occupancy_change_pct / 100)
            feat_sc["bed_occ_lag1"] = _safe_numeric(feat_sc["bed_occ_lag1"]) * (1 + occupancy_change_pct / 100)
        if adr_change_pct:
            feat_sc["adr_lag1"] = _safe_numeric(feat_sc["adr_lag1"]) * (1 + adr_change_pct / 100)
            feat_sc["revpar_lag1"] = _safe_numeric(feat_sc["revpar_lag1"]) * (1 + adr_change_pct / 100)
        if foreign_ratio_change_pct:
            feat_sc["foreign_ratio"] = _safe_numeric(feat_sc["foreign_ratio"], 0.5) * (1 + foreign_ratio_change_pct / 100)
        return feat_sc

    @staticmethod
    def _compute_impact(
        baseline: list[dict], scenario: list[dict]
    ) -> dict:
        """Compute delta/impact metrics between baseline and scenario."""
        avg_baseline = np.mean([b["value"] for b in baseline])
        avg_scenario = np.mean([s["value"] for s in scenario])
        avg_change_pct = (
            round((avg_scenario - avg_baseline) / avg_baseline * 100, 2)
            if avg_baseline != 0
            else 0.0
        )
        return {
            "avg_baseline": round(avg_baseline),
            "avg_scenario": round(avg_scenario),
            "avg_change_pct": avg_change_pct,
        }

    def predict_scenario(
        self,
        db: Session,
        occupancy_change_pct: float = 0.0,
        adr_change_pct: float = 0.0,
        foreign_ratio_change_pct: float = 0.0,
        horizon: int = 12,
    ) -> dict:
        """Run what-if scenario.

        Returns baseline and scenario forecasts.
        """
        self._ensure_fitted(db)

        with self._predict_lock:
            df = self.latest_df.copy()
            features = self.latest_features.copy() if self.latest_features is not None else None
        last_period = pd.Period(df.index[-1], freq="M")
        future_periods = pd.period_range(last_period + 1, periods=horizon, freq="M")

        baseline: list[dict] = []
        scenario: list[dict] = []
        residual_std = self._residual_std

        ext_df = df.copy()
        for h, period in enumerate(future_periods, start=1):
            period_str = str(period)

            feat = self._build_period_features(ext_df, period)

            # Standard error grows with the square root of horizon
            se = residual_std * np.sqrt(h) if residual_std > 0 else 0.0

            # Baseline prediction
            X_base = pd.DataFrame([feat], columns=self.feature_names).fillna(0)
            base_pred = float(self.model.predict(X_base)[0])
            base_point: dict = {"period": period_str, "value": round(base_pred)}
            if se > 0:
                base_point["ci_lower_80"] = round(base_pred - 1.28 * se)
                base_point["ci_upper_80"] = round(base_pred + 1.28 * se)
                base_point["ci_lower_95"] = round(base_pred - 1.96 * se)
                base_point["ci_upper_95"] = round(base_pred + 1.96 * se)
            baseline.append(base_point)

            # Scenario prediction
            feat_sc = self._apply_scenario(
                feat, occupancy_change_pct, adr_change_pct, foreign_ratio_change_pct
            )
            X_sc = pd.DataFrame([feat_sc], columns=self.feature_names).fillna(0)
            sc_pred = float(self.model.predict(X_sc)[0])
            sc_point: dict = {"period": period_str, "value": round(sc_pred)}
            if se > 0:
                sc_point["ci_lower_80"] = round(sc_pred - 1.28 * se)
                sc_point["ci_upper_80"] = round(sc_pred + 1.28 * se)
                sc_point["ci_lower_95"] = round(sc_pred - 1.96 * se)
                sc_point["ci_upper_95"] = round(sc_pred + 1.96 * se)
            scenario.append(sc_point)

            # Extend for next iteration
            last_foreign_ratio = feat["foreign_ratio"]
            new_row: dict = {
                "arrivals": base_pred,
                "foreign": base_pred * last_foreign_ratio,
            }
            for col_name in ACCOM_INDICATORS.values():
                new_row[col_name] = _safe_numeric(ext_df[col_name].iloc[-1])
            ext_df.loc[period_str] = new_row

        return {
            "baseline_forecast": baseline,
            "scenario_forecast": scenario,
            "impact_summary": self._compute_impact(baseline, scenario),
            "params": {
                "occupancy_change_pct": occupancy_change_pct,
                "adr_change_pct": adr_change_pct,
                "foreign_ratio_change_pct": foreign_ratio_change_pct,
            },
        }
