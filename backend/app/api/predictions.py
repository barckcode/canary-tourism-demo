"""Prediction and forecast endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelMetric, Prediction
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


@router.get("")
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
        )
        .order_by(Prediction.period)
        .limit(horizon)
        .all()
    )

    # Fetch metrics for the requested model
    all_metrics = _get_metrics(db, indicator, geo)
    model_metrics = all_metrics.get(model)

    return {
        "forecast": [
            {
                "period": r.period,
                "value": r.value_predicted,
                "ci_lower_80": r.ci_lower_80,
                "ci_upper_80": r.ci_upper_80,
                "ci_lower_95": r.ci_lower_95,
                "ci_upper_95": r.ci_upper_95,
            }
            for r in results
        ],
        "model_info": {
            "name": model,
            "total_periods": len(results),
            "metrics": model_metrics,
        },
    }


@router.get("/compare")
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
                }
                for r in results
            ]

    return {
        "models": models,
        "metrics": all_metrics,
    }
