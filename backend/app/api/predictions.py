"""Prediction and forecast endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    PredictionCompareResponse,
    PredictionHistoryResponse,
    PredictionResponse,
    TrainingInfoResponse,
    RetrainResponse,
)
from app.db.database import get_db
from app.db.models import ModelMetric, Prediction, TrainingRun
from app.rate_limit import limiter

router = APIRouter()


def _get_metrics(db: Session, indicator: str, geo: str) -> dict[str, dict]:
    """Load accuracy metrics for all models from the database."""
    rows = (
        db.query(ModelMetric)
        .filter(
            ModelMetric.indicator == indicator,
            ModelMetric.geo_code == geo,
        )
        .all()
    )
    return {
        r.model: {
            "rmse": r.rmse,
            "mae": r.mae,
            "mape": r.mape,
            "test_size": r.test_size,
        }
        for r in rows
    }


@router.get("", response_model=PredictionResponse)
@limiter.limit("20/minute")
def get_predictions(
    request: Request,
    indicator: str = Query("turistas", description="Indicator to forecast"),
    geo: str = Query("ES709", description="Geographic code"),
    horizon: int = Query(12, ge=1, le=60, description="Forecast horizon in months"),
    model: str = Query("ensemble", description="Model name"),
    db: Session = Depends(get_db),
):
    """Return pre-computed forecast for the given parameters.

    Includes accuracy metrics (RMSE, MAE, MAPE) computed via
    hold-out validation on the last 12 months of non-COVID data.
    """
    results = (
        db.query(Prediction)
        .filter(
            Prediction.model == model,
            Prediction.indicator == indicator,
            Prediction.geo_code == geo,
            Prediction.is_current == True,  # noqa: E712
        )
        .order_by(Prediction.period)
        .limit(horizon)
        .all()
    )

    # Fetch metrics for the requested model
    all_metrics = _get_metrics(db, indicator, geo)
    model_metrics = all_metrics.get(model)

    actual_horizon = len(results)

    return {
        "forecast": [
            {
                "period": r.period,
                "value": r.value_predicted,
                "ci_lower_80": r.ci_lower_80,
                "ci_upper_80": r.ci_upper_80,
                "ci_lower_95": r.ci_lower_95,
                "ci_upper_95": r.ci_upper_95,
                "ci_available": r.ci_lower_80 is not None and r.ci_upper_80 is not None,
            }
            for r in results
        ],
        "model_info": {
            "name": model,
            "total_periods": actual_horizon,
            "metrics": model_metrics,
        },
        "requested_horizon": horizon,
        "actual_horizon": actual_horizon,
        "complete": actual_horizon >= horizon,
    }


@router.get("/compare", response_model=PredictionCompareResponse)
@limiter.limit("20/minute")
def compare_models(
    request: Request,
    indicator: str = Query("turistas"),
    geo: str = Query("ES709"),
    horizon: int = Query(12, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """Compare forecasts from all available models.

    Each model entry includes its forecast points and accuracy metrics.
    The ``metrics`` key contains per-model RMSE, MAE, and MAPE values
    from hold-out evaluation on the last 12 non-COVID months.
    """
    all_metrics = _get_metrics(db, indicator, geo)

    models = {}
    for model_name in ["sarima", "holt_winters", "seasonal_naive", "ensemble"]:
        results = (
            db.query(Prediction)
            .filter(
                Prediction.model == model_name,
                Prediction.indicator == indicator,
                Prediction.geo_code == geo,
                Prediction.is_current == True,  # noqa: E712
            )
            .order_by(Prediction.period)
            .limit(horizon)
            .all()
        )
        if results:
            models[model_name] = [
                {
                    "period": r.period,
                    "value": r.value_predicted,
                    "ci_lower_80": r.ci_lower_80,
                    "ci_upper_80": r.ci_upper_80,
                    "ci_lower_95": r.ci_lower_95,
                    "ci_upper_95": r.ci_upper_95,
                    "ci_available": r.ci_lower_80 is not None and r.ci_upper_80 is not None,
                }
                for r in results
            ]

    return {
        "models": models,
        "metrics": all_metrics,
    }


@router.post("/retrain", response_model=RetrainResponse)
@limiter.limit("2/minute")
def retrain_models(
    request: Request,
    db: Session = Depends(get_db),
):
    """Force model retraining.

    Triggers a full retraining of all ML models (SARIMA, HW, Naive,
    Ensemble, K-Means profiler, GBR scenario engine) regardless of
    whether new data has arrived.
    """
    from app.models.trainer import retrain_if_needed

    result = retrain_if_needed(db, force=True)
    return result


@router.get("/training-info", response_model=TrainingInfoResponse)
@limiter.limit("20/minute")
def get_training_info(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get information about when models were last trained.

    Returns the timestamp of the last successful training run,
    the data range it was trained on, and the list of models trained.
    """
    latest = (
        db.query(TrainingRun)
        .filter(TrainingRun.status == "success")
        .order_by(TrainingRun.trained_at.desc())
        .first()
    )

    if latest is None:
        return {
            "trained_at": None,
            "data_up_to": None,
            "status": "no_training",
            "models_trained": [],
            "duration_seconds": None,
        }

    import json
    models = json.loads(latest.models_trained) if latest.models_trained else []

    return {
        "trained_at": latest.trained_at,
        "data_up_to": latest.data_up_to,
        "status": latest.status,
        "models_trained": models,
        "duration_seconds": latest.duration_seconds,
    }


@router.get("/history", response_model=PredictionHistoryResponse)
@limiter.limit("20/minute")
def get_prediction_history(
    request: Request,
    model: str = Query("ensemble", description="Model name"),
    indicator: str = Query("turistas", description="Indicator"),
    geo: str = Query("ES709", description="Geographic code"),
    limit: int = Query(5, ge=1, le=20, description="Number of past versions to return"),
    db: Session = Depends(get_db),
):
    """Return the last N versions of predictions for a model/indicator.

    Allows comparison of how forecasts have changed across training runs.
    Each version includes the forecast points and the version metadata
    (version number and trained_at timestamp).
    """
    from sqlalchemy import distinct

    # Get the last N distinct versions, ordered newest first
    version_rows = (
        db.query(distinct(Prediction.version), Prediction.trained_at)
        .filter(
            Prediction.model == model,
            Prediction.indicator == indicator,
            Prediction.geo_code == geo,
        )
        .order_by(Prediction.version.desc())
        .limit(limit)
        .all()
    )

    versions = []
    for version_num, trained_at in version_rows:
        rows = (
            db.query(Prediction)
            .filter(
                Prediction.model == model,
                Prediction.indicator == indicator,
                Prediction.geo_code == geo,
                Prediction.version == version_num,
            )
            .order_by(Prediction.period)
            .all()
        )
        versions.append({
            "version": version_num,
            "trained_at": str(trained_at) if trained_at else None,
            "is_current": rows[0].is_current if rows else False,
            "forecast": [
                {
                    "period": r.period,
                    "value": r.value_predicted,
                    "ci_lower_80": r.ci_lower_80,
                    "ci_upper_80": r.ci_upper_80,
                    "ci_lower_95": r.ci_lower_95,
                    "ci_upper_95": r.ci_upper_95,
                    "ci_available": r.ci_lower_80 is not None and r.ci_upper_80 is not None,
                }
                for r in rows
            ],
        })

    return {
        "model": model,
        "indicator": indicator,
        "geo_code": geo,
        "total_versions": len(versions),
        "versions": versions,
    }
