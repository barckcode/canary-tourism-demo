"""API router aggregator."""

from fastapi import APIRouter

from app.api import dashboard, predictions, profiles, scenarios, timeseries

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(timeseries.router, prefix="/timeseries", tags=["timeseries"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])
api_router.include_router(scenarios.router, prefix="/scenarios", tags=["scenarios"])
