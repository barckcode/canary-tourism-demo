"""Model training and retraining orchestrator.

Coordinates training of all ML models (SARIMA, HW, GBR, K-Means),
saves serialized models, and stores predictions in the database.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import joblib
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import TrainingRun
from app.models.forecaster import Forecaster
from app.models.profiler import TouristProfiler
from app.models.scenario_engine import ScenarioEngine
from app.utils.queries import load_arrivals_series

logger = logging.getLogger(__name__)


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


def _store_metrics(db: Session, metrics: dict, indicator: str, geo_code: str,
                   test_size: int) -> None:
    """Persist model accuracy metrics to the model_metrics table."""
    from app.models.forecaster import ModelMetrics  # avoid circular at module level

    for model_name, m in metrics.items():
        if not isinstance(m, ModelMetrics):
            continue
        db.execute(
            text("""
                INSERT OR REPLACE INTO model_metrics
                    (model, indicator, geo_code, rmse, mae, mape, test_size)
                VALUES (:model, :indicator, :geo, :rmse, :mae, :mape, :ts)
            """),
            {
                "model": model_name,
                "indicator": indicator,
                "geo": geo_code,
                "rmse": m.rmse,
                "mae": m.mae,
                "mape": m.mape,
                "ts": test_size,
            },
        )
    logger.info("Stored metrics for %d models.", len(metrics))


def train_forecaster(db: Session, horizon: int = 12) -> dict:
    """Train SARIMA + HW + Naive forecaster and store predictions."""
    logger.info("Loading arrivals time series...")
    series = load_arrivals_series(db)
    logger.info("Loaded %d monthly observations (%s to %s).",
                len(series), series.index[0], series.index[-1])

    forecaster = Forecaster()
    forecaster.fit(series, exclude_covid=True)

    # Evaluate accuracy on held-out test set (last 12 non-COVID months)
    metrics = forecaster.evaluate(test_size=12)
    _store_metrics(db, metrics, "turistas", "ES709", test_size=12)

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


def _get_data_hash(db: Session) -> str:
    """Compute a hash of key training data for change detection."""
    row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt, MAX(period) AS max_period, MAX(fetched_at) AS max_fetched
            FROM time_series
        """)
    ).fetchone()
    raw = f"{row.cnt}|{row.max_period}|{row.max_fetched}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_latest_data_period(db: Session) -> str | None:
    """Get the latest period in the time_series table."""
    row = db.execute(
        text("SELECT MAX(fetched_at) AS latest FROM time_series")
    ).fetchone()
    return row.latest if row else None


def _get_latest_training(db: Session) -> TrainingRun | None:
    """Get the most recent successful training run."""
    return (
        db.query(TrainingRun)
        .filter(TrainingRun.status == "success")
        .order_by(TrainingRun.trained_at.desc())
        .first()
    )


def needs_retraining(db: Session) -> bool:
    """Check whether models need retraining.

    Returns True if:
    - No successful training run exists, or
    - The data hash has changed since the last training (new data arrived).
    """
    latest_training = _get_latest_training(db)
    if latest_training is None:
        return True

    current_hash = _get_data_hash(db)
    return current_hash != latest_training.data_hash


def retrain_if_needed(db: Session, force: bool = False) -> dict:
    """Retrain models if new data has arrived or if forced.

    Args:
        db: Database session.
        force: If True, retrain regardless of data changes.

    Returns:
        Dict with retraining status information.
    """
    should_retrain = force or needs_retraining(db)

    if not should_retrain:
        latest = _get_latest_training(db)
        return {
            "retrained": False,
            "reason": "No new data since last training.",
            "last_trained_at": latest.trained_at if latest else None,
            "data_up_to": latest.data_up_to if latest else None,
        }

    logger.info("Starting model retraining (force=%s)...", force)
    start = time.monotonic()
    data_hash = _get_data_hash(db)
    latest_period = _get_latest_data_period(db)
    trained_at = datetime.now(timezone.utc).isoformat()

    try:
        trainer = ModelTrainer()
        trainer.train_all(db)
        duration = time.monotonic() - start

        run = TrainingRun(
            trained_at=trained_at,
            data_up_to=latest_period,
            data_hash=data_hash,
            models_trained=json.dumps(["sarima", "holt_winters", "seasonal_naive",
                                       "ensemble", "profiler", "scenario_engine"]),
            status="success",
            duration_seconds=round(duration, 2),
        )
        db.add(run)
        db.commit()

        logger.info("Model retraining completed in %.1fs.", duration)
        return {
            "retrained": True,
            "trained_at": trained_at,
            "data_up_to": latest_period,
            "duration_seconds": round(duration, 2),
            "models_trained": ["sarima", "holt_winters", "seasonal_naive",
                               "ensemble", "profiler", "scenario_engine"],
        }

    except Exception as exc:
        duration = time.monotonic() - start
        error_msg = str(exc)
        logger.exception("Model retraining failed after %.1fs.", duration)

        run = TrainingRun(
            trained_at=trained_at,
            data_up_to=latest_period,
            data_hash=data_hash,
            models_trained=json.dumps([]),
            status="error",
            error_message=error_msg,
            duration_seconds=round(duration, 2),
        )
        db.add(run)
        db.commit()

        return {
            "retrained": False,
            "reason": f"Training failed: {error_msg}",
            "duration_seconds": round(duration, 2),
        }
