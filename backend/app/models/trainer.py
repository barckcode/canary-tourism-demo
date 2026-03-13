"""Model training and retraining orchestrator.

Coordinates training of all ML models (SARIMA, HW, GBR, K-Means),
saves serialized models, and stores predictions in the database.
"""

import json
import logging
import re

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.models.forecaster import Forecaster
from app.models.profiler import TouristProfiler
from app.models.scenario_engine import ScenarioEngine

logger = logging.getLogger(__name__)


def _load_arrivals_series(db: Session) -> pd.Series:
    """Load monthly tourist arrivals from DB as a pandas Series with PeriodIndex."""
    rows = db.execute(
        text("""
            SELECT period, value FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
            ORDER BY period
        """)
    ).fetchall()

    # Filter only YYYY-MM format (exclude annual totals)
    monthly = [(r.period, r.value) for r in rows if re.match(r"^\d{4}-\d{2}$", r.period)]

    periods = pd.PeriodIndex([p for p, _ in monthly], freq="M")
    values = np.array([v for _, v in monthly], dtype=float)

    return pd.Series(values, index=periods, name="turistas")


def _store_predictions(db: Session, model_name: str, indicator: str,
                       geo_code: str, forecast) -> int:
    """Store forecast results in the predictions table."""
    # Clear old predictions for this model/indicator
    db.execute(
        text("""
            DELETE FROM predictions
            WHERE model=:model AND indicator=:indicator AND geo_code=:geo
        """),
        {"model": model_name, "indicator": indicator, "geo": geo_code},
    )

    count = 0
    for i, period in enumerate(forecast.periods):
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted,
                     ci_lower_80, ci_upper_80, ci_lower_95, ci_upper_95)
                VALUES (:model, :indicator, :geo, :period, :value,
                        :ci_lo80, :ci_hi80, :ci_lo95, :ci_hi95)
            """),
            {
                "model": model_name,
                "indicator": indicator,
                "geo": geo_code,
                "period": period,
                "value": float(forecast.values[i]),
                "ci_lo80": float(forecast.ci_lower_80[i]),
                "ci_hi80": float(forecast.ci_upper_80[i]),
                "ci_lo95": float(forecast.ci_lower_95[i]),
                "ci_hi95": float(forecast.ci_upper_95[i]),
            },
        )
        count += 1

    return count


def train_forecaster(db: Session, horizon: int = 12) -> dict:
    """Train SARIMA + HW + Naive forecaster and store predictions."""
    logger.info("Loading arrivals time series...")
    series = _load_arrivals_series(db)
    logger.info("Loaded %d monthly observations (%s to %s).",
                len(series), series.index[0], series.index[-1])

    forecaster = Forecaster()
    forecaster.fit(series, exclude_covid=True)

    # Generate forecasts from all models
    results = {}
    for name, method in [
        ("sarima", forecaster.predict_sarima),
        ("holt_winters", forecaster.predict_hw),
        ("seasonal_naive", forecaster.predict_naive),
        ("ensemble", forecaster.predict),
    ]:
        fc = method(horizon)
        count = _store_predictions(db, name, "turistas", "ES709", fc)
        results[name] = count
        logger.info("Stored %d predictions for model '%s'.", count, name)

    db.commit()

    # Save model to disk
    model_path = settings.models_dir / "forecaster.pkl"
    joblib.dump(forecaster, model_path)
    logger.info("Saved forecaster to %s", model_path)

    return results


def train_profiler(db: Session, n_clusters: int = 4) -> dict:
    """Train K-Means profiler on microdata and store profiles."""
    logger.info("Loading microdata for profiling...")
    rows = db.execute(
        text("SELECT raw_json FROM microdata WHERE raw_json IS NOT NULL")
    ).fetchall()
    raw_jsons = [r[0] for r in rows]
    logger.info("Loaded %d microdata records.", len(raw_jsons))

    profiler = TouristProfiler(n_clusters=n_clusters)
    labels = profiler.fit(raw_jsons)

    # Update microdata with cluster assignments
    ids = db.execute(text("SELECT id FROM microdata ORDER BY id")).fetchall()
    for row_id, label in zip(ids, labels):
        db.execute(
            text("UPDATE microdata SET cluster_id=:cid WHERE id=:id"),
            {"cid": int(label), "id": row_id[0]},
        )

    # Store profiles
    profiles = profiler.get_profiles()
    db.execute(text("DELETE FROM profiles"))
    for p in profiles:
        db.execute(
            text("""
                INSERT INTO profiles
                    (cluster_id, cluster_name, size_pct, avg_age, avg_spend,
                     avg_nights, top_nationalities, top_accommodations,
                     top_activities, top_motivations, characteristics)
                VALUES (:cid, :name, :size, :age, :spend, :nights,
                        :nat, :acc, :act, :mot, :chars)
            """),
            {
                "cid": p["cluster_id"],
                "name": p["cluster_name"],
                "size": p["size_pct"],
                "age": p["avg_age"],
                "spend": p["avg_spend"],
                "nights": p["avg_nights"],
                "nat": json.dumps(p["top_nationalities"]),
                "acc": json.dumps(p["top_accommodations"]),
                "act": json.dumps(p["top_activities"]),
                "mot": json.dumps(p["top_motivations"]),
                "chars": json.dumps(p["characteristics"]),
            },
        )

    db.commit()

    # Save model
    model_path = settings.models_dir / "profiler.pkl"
    joblib.dump(profiler, model_path)
    logger.info("Saved profiler to %s", model_path)

    return {"n_clusters": n_clusters, "n_records": len(labels), "profiles": len(profiles)}


def train_scenario_engine(db: Session) -> dict:
    """Train GBR scenario engine."""
    engine = ScenarioEngine()
    engine.fit(db)

    model_path = settings.models_dir / "scenario_engine.pkl"
    joblib.dump(engine, model_path)
    logger.info("Saved scenario engine to %s", model_path)

    return {"status": "trained", "features": len(engine.feature_names)}


class ModelTrainer:
    """Orchestrates training/retraining of all models."""

    def train_all(self, db: Session):
        """Train all models and store predictions."""
        results = {}
        results["forecaster"] = train_forecaster(db)
        results["profiler"] = train_profiler(db)
        results["scenario_engine"] = train_scenario_engine(db)
        return results
