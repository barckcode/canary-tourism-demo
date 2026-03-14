"""Scenario engine endpoints (GBR what-if analysis)."""

import threading

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.scenario_engine import ScenarioEngine
from app.rate_limit import limiter

router = APIRouter()

# Module-level singleton — loaded once, reused across requests
_engine: ScenarioEngine | None = None
_engine_lock = threading.Lock()


def _get_engine(db: Session) -> ScenarioEngine:
    global _engine
    if _engine is not None and _engine.is_fitted:
        return _engine
    with _engine_lock:
        # Double-check after acquiring the lock
        if _engine is not None and _engine.is_fitted:
            return _engine
        _engine = ScenarioEngine()
        _engine.predict_scenario(db=db, horizon=1)  # triggers lazy load from pkl
    return _engine


class ScenarioRequest(BaseModel):
    occupancy_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    adr_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    foreign_ratio_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    horizon: int = Field(12, ge=1, le=60)


@router.post("")
@limiter.limit("20/minute")
def run_scenario(
    request: Request,
    scenario: ScenarioRequest,
    db: Session = Depends(get_db),
):
    """Run a what-if scenario using the GBR model."""
    engine = _get_engine(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=scenario.occupancy_change_pct,
        adr_change_pct=scenario.adr_change_pct,
        foreign_ratio_change_pct=scenario.foreign_ratio_change_pct,
        horizon=scenario.horizon,
    )
    return result
