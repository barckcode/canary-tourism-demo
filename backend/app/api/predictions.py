"""Prediction and forecast endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Prediction
from app.rate_limit import limiter

router = APIRouter()


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
    """Return pre-computed forecast for the given parameters."""
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
    """Compare forecasts from all available models."""
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

    return {"models": models}
