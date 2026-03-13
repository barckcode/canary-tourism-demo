"""GBR scenario engine for what-if analysis.

Uses Gradient Boosting Regressor trained on multivariate features
(lagged arrivals, accommodation metrics) to enable what-if scenario
exploration with user-adjustable inputs.
"""

import logging
import re

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

# COVID exclusion range
COVID_START = "2020-03"
COVID_END = "2021-06"

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
    # Arrivals
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
            ORDER BY period
        """)
    ).fetchall()
    monthly = [(r.period, r.value) for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)]
    df = pd.DataFrame(monthly, columns=["period", "arrivals"])
    df = df.set_index("period")

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

    # Foreign ratio
    features["foreign_ratio"] = df["foreign"] / df["arrivals"]

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
        if not self.is_fitted:
            # Try loading from disk
            model_path = settings.models_dir / "scenario_engine.pkl"
            if model_path.exists():
                saved = joblib.load(model_path)
                self.model = saved.model
                self.feature_names = saved.feature_names
                self.latest_df = saved.latest_df
                self.latest_features = saved.latest_features
                self.is_fitted = True
            else:
                self.fit(db)

        df = self.latest_df
        features = self.latest_features

        last_period = pd.Period(df.index[-1], freq="M")
        future_periods = pd.period_range(last_period + 1, periods=horizon, freq="M")

        baseline = []
        scenario = []

        # Extend data iteratively
        ext_df = df.copy()
        for period in future_periods:
            period_str = str(period)

            # Build feature row for this period
            feat = {}
            arrivals_series = pd.Series(
                {p: ext_df.loc[p, "arrivals"] for p in ext_df.index},
            )

            for lag in [1, 3, 6, 12]:
                idx = len(arrivals_series) - lag
                feat[f"y_lag{lag}"] = arrivals_series.iloc[idx] if idx >= 0 else np.nan

            feat["rolling_3m"] = arrivals_series.iloc[-3:].mean()
            feat["rolling_12m"] = arrivals_series.iloc[-12:].mean()

            last_foreign_ratio = (
                ext_df["foreign"].iloc[-1] / ext_df["arrivals"].iloc[-1]
                if ext_df["arrivals"].iloc[-1] else 0.5
            )
            feat["foreign_ratio"] = last_foreign_ratio

            for col_name in ACCOM_INDICATORS.values():
                feat[f"{col_name}_lag1"] = ext_df[col_name].iloc[-1]

            feat["month"] = period.month
            feat["month_sin"] = np.sin(2 * np.pi * period.month / 12)
            feat["month_cos"] = np.cos(2 * np.pi * period.month / 12)

            # Baseline prediction
            X_base = pd.DataFrame([feat], columns=self.feature_names)
            X_base = X_base.fillna(0)
            base_pred = float(self.model.predict(X_base)[0])
            baseline.append({"period": period_str, "value": round(base_pred)})

            # Scenario prediction (modify features)
            feat_sc = feat.copy()
            if occupancy_change_pct:
                feat_sc["room_occ_lag1"] *= (1 + occupancy_change_pct / 100)
                feat_sc["bed_occ_lag1"] *= (1 + occupancy_change_pct / 100)
            if adr_change_pct:
                feat_sc["adr_lag1"] *= (1 + adr_change_pct / 100)
                feat_sc["revpar_lag1"] *= (1 + adr_change_pct / 100)
            if foreign_ratio_change_pct:
                feat_sc["foreign_ratio"] *= (1 + foreign_ratio_change_pct / 100)

            X_sc = pd.DataFrame([feat_sc], columns=self.feature_names)
            X_sc = X_sc.fillna(0)
            sc_pred = float(self.model.predict(X_sc)[0])
            scenario.append({"period": period_str, "value": round(sc_pred)})

            # Extend for next iteration
            new_row = {
                "arrivals": base_pred,
                "foreign": base_pred * last_foreign_ratio,
            }
            for col_name in ACCOM_INDICATORS.values():
                new_row[col_name] = ext_df[col_name].iloc[-1]
            ext_df.loc[period_str] = new_row

        impact = {
            "avg_baseline": round(np.mean([b["value"] for b in baseline])),
            "avg_scenario": round(np.mean([s["value"] for s in scenario])),
            "avg_change_pct": round(
                (np.mean([s["value"] for s in scenario])
                 - np.mean([b["value"] for b in baseline]))
                / np.mean([b["value"] for b in baseline])
                * 100,
                2,
            ),
        }

        return {
            "baseline_forecast": baseline,
            "scenario_forecast": scenario,
            "impact_summary": impact,
            "params": {
                "occupancy_change_pct": occupancy_change_pct,
                "adr_change_pct": adr_change_pct,
                "foreign_ratio_change_pct": foreign_ratio_change_pct,
            },
        }
