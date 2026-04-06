"""Scenario engine endpoints (GBR what-if analysis).

Provides endpoints for running, saving, listing, comparing, and deleting
what-if scenarios, plus feature importance inspection.
"""

import json
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.schemas import (
    CompareResponse,
    FeatureImportanceResponse,
    SavedScenarioDetail,
    SavedScenarioListResponse,
    SavedScenarioSummary,
    ScenarioResponse,
)
from app.db.database import get_db
from app.db.models import SavedScenario
from app.models.scenario_engine import ScenarioEngine
from app.rate_limit import limiter

router = APIRouter()

# Module-level singleton — loaded once, reused across requests
_engine: ScenarioEngine | None = None
_engine_lock = threading.Lock()


def _get_engine(db: Session) -> ScenarioEngine:
    """Get or create the ScenarioEngine singleton.

    WARNING: May trigger full model training on first call if no
    persisted model exists. Subsequent calls load from pickle.
    """
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


class SaveScenarioRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    occupancy_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    adr_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    foreign_ratio_change_pct: float = Field(0.0, ge=-50.0, le=50.0)
    horizon: int = Field(12, ge=1, le=60)


class CompareRequest(BaseModel):
    scenario_ids: list[int] = Field(..., min_length=1, max_length=3)


# ---------------------------------------------------------------------------
# Existing endpoint
# ---------------------------------------------------------------------------


@router.post("", response_model=ScenarioResponse)
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


# ---------------------------------------------------------------------------
# Save a scenario
# ---------------------------------------------------------------------------


@router.post("/save", response_model=SavedScenarioDetail)
@limiter.limit("20/minute")
def save_scenario(
    request: Request,
    body: SaveScenarioRequest,
    db: Session = Depends(get_db),
):
    """Run a what-if scenario and persist it with a name.

    The scenario is executed, and both the parameters and the full result
    are stored for later retrieval and comparison.
    """
    engine = _get_engine(db)
    result = engine.predict_scenario(
        db=db,
        occupancy_change_pct=body.occupancy_change_pct,
        adr_change_pct=body.adr_change_pct,
        foreign_ratio_change_pct=body.foreign_ratio_change_pct,
        horizon=body.horizon,
    )

    saved = SavedScenario(
        name=body.name,
        occupancy_change_pct=body.occupancy_change_pct,
        adr_change_pct=body.adr_change_pct,
        foreign_ratio_change_pct=body.foreign_ratio_change_pct,
        horizon=body.horizon,
        result_json=json.dumps(result),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    return _to_detail(saved, result)


# ---------------------------------------------------------------------------
# List saved scenarios
# ---------------------------------------------------------------------------


@router.get("/saved", response_model=SavedScenarioListResponse)
@limiter.limit("30/minute")
def list_saved_scenarios(
    request: Request,
    db: Session = Depends(get_db),
):
    """List all saved scenarios (lightweight, without full results)."""
    rows = (
        db.query(SavedScenario)
        .order_by(SavedScenario.created_at.desc())
        .all()
    )
    return SavedScenarioListResponse(
        scenarios=[_to_summary(r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Get a single saved scenario
# ---------------------------------------------------------------------------


@router.get("/saved/{scenario_id}", response_model=SavedScenarioDetail)
@limiter.limit("30/minute")
def get_saved_scenario(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve a saved scenario with its full result."""
    saved = db.query(SavedScenario).filter(SavedScenario.id == scenario_id).first()
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved scenario not found")
    result = json.loads(saved.result_json) if saved.result_json else {}
    return _to_detail(saved, result)


# ---------------------------------------------------------------------------
# Delete a saved scenario
# ---------------------------------------------------------------------------


@router.delete("/saved/{scenario_id}", status_code=204)
@limiter.limit("20/minute")
def delete_saved_scenario(
    request: Request,
    scenario_id: int,
    db: Session = Depends(get_db),
):
    """Delete a saved scenario by ID."""
    saved = db.query(SavedScenario).filter(SavedScenario.id == scenario_id).first()
    if saved is None:
        raise HTTPException(status_code=404, detail="Saved scenario not found")
    db.delete(saved)
    db.commit()


# ---------------------------------------------------------------------------
# Compare multiple saved scenarios
# ---------------------------------------------------------------------------


@router.post("/compare", response_model=CompareResponse)
@limiter.limit("20/minute")
def compare_scenarios(
    request: Request,
    body: CompareRequest,
    db: Session = Depends(get_db),
):
    """Compare up to 3 saved scenarios side-by-side.

    Returns the full result for each requested scenario, keyed by its ID.
    """
    rows = (
        db.query(SavedScenario)
        .filter(SavedScenario.id.in_(body.scenario_ids))
        .all()
    )
    found_ids = {r.id for r in rows}
    missing = set(body.scenario_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Scenarios not found: {sorted(missing)}",
        )

    scenarios = {}
    for row in rows:
        result = json.loads(row.result_json) if row.result_json else {}
        scenarios[str(row.id)] = _to_detail(row, result)

    return CompareResponse(scenarios=scenarios)


# ---------------------------------------------------------------------------
# Feature importance
# ---------------------------------------------------------------------------


@router.get("/feature-importance", response_model=FeatureImportanceResponse)
@limiter.limit("30/minute")
def get_feature_importance(
    request: Request,
    db: Session = Depends(get_db),
):
    """Return the GBR model's feature importances.

    Each feature name is mapped to its importance score (sum to 1.0).
    """
    engine = _get_engine(db)
    if engine.model is None or not hasattr(engine.model, "feature_importances_"):
        raise HTTPException(
            status_code=500,
            detail="Model not available or has no feature importances",
        )
    importances = dict(
        zip(engine.feature_names, [float(v) for v in engine.model.feature_importances_])
    )
    return FeatureImportanceResponse(importances=importances)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_summary(row: SavedScenario) -> SavedScenarioSummary:
    return SavedScenarioSummary(
        id=row.id,
        name=row.name,
        occupancy_change_pct=row.occupancy_change_pct or 0.0,
        adr_change_pct=row.adr_change_pct or 0.0,
        foreign_ratio_change_pct=row.foreign_ratio_change_pct or 0.0,
        horizon=row.horizon or 12,
        created_at=row.created_at,
    )


def _to_detail(row: SavedScenario, result: dict) -> SavedScenarioDetail:
    return SavedScenarioDetail(
        id=row.id,
        name=row.name,
        occupancy_change_pct=row.occupancy_change_pct or 0.0,
        adr_change_pct=row.adr_change_pct or 0.0,
        foreign_ratio_change_pct=row.foreign_ratio_change_pct or 0.0,
        horizon=row.horizon or 12,
        created_at=row.created_at,
        result=result,
    )
