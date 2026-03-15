"""Tests for saved scenario CRUD endpoints and feature importance."""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from app.db.models import SavedScenario
from app.models.scenario_engine import ACCOM_INDICATORS, ScenarioEngine


def _make_fitted_engine():
    """Build a ScenarioEngine with a fake model and synthetic latest_df."""
    periods = pd.period_range("2022-01", periods=24, freq="M")
    period_strs = [str(p) for p in periods]

    np.random.seed(42)
    arrivals = np.random.uniform(300_000, 500_000, size=24)
    foreign = arrivals * np.random.uniform(0.6, 0.8, size=24)

    data = {"arrivals": arrivals, "foreign": foreign}
    for col_name in ACCOM_INDICATORS.values():
        data[col_name] = np.random.uniform(10, 100, size=24)

    df = pd.DataFrame(data, index=period_strs)

    feature_names = []
    for lag in [1, 3, 6, 12]:
        feature_names.append(f"y_lag{lag}")
    feature_names.extend(["rolling_3m", "rolling_12m", "foreign_ratio"])
    for col_name in ACCOM_INDICATORS.values():
        feature_names.append(f"{col_name}_lag1")
    feature_names.extend(["month", "month_sin", "month_cos"])

    n_features = len(feature_names)
    X_train = np.random.rand(20, n_features)
    y_train = np.random.uniform(300_000, 500_000, size=20)
    model = GradientBoostingRegressor(n_estimators=10, max_depth=2, random_state=42)
    model.fit(X_train, y_train)

    engine = ScenarioEngine()
    engine.model = model
    engine.feature_names = feature_names
    engine.latest_df = df
    engine.latest_features = pd.DataFrame(
        np.random.rand(24, n_features),
        index=period_strs,
        columns=feature_names,
    )
    engine.is_fitted = True
    return engine


def _patch_engine():
    """Context manager that patches the scenario engine singleton."""
    engine = _make_fitted_engine()
    return patch("app.api.scenarios._get_engine", return_value=engine)


# ---------------------------------------------------------------------------
# POST /api/scenarios/save
# ---------------------------------------------------------------------------


def test_save_scenario(client):
    """Saving a scenario should persist it and return full result."""
    with _patch_engine():
        resp = client.post("/api/scenarios/save", json={
            "name": "Test scenario 1",
            "occupancy_change_pct": 5.0,
            "adr_change_pct": -2.0,
            "foreign_ratio_change_pct": 1.0,
            "horizon": 6,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test scenario 1"
    assert data["occupancy_change_pct"] == 5.0
    assert data["adr_change_pct"] == -2.0
    assert data["horizon"] == 6
    assert "id" in data
    assert "result" in data
    assert "baseline_forecast" in data["result"]
    assert "scenario_forecast" in data["result"]


def test_save_scenario_name_required(client):
    """Saving without a name should return 422."""
    with _patch_engine():
        resp = client.post("/api/scenarios/save", json={
            "occupancy_change_pct": 5.0,
        })
    assert resp.status_code == 422


def test_save_scenario_name_too_long(client):
    """Name exceeding 100 characters should return 422."""
    with _patch_engine():
        resp = client.post("/api/scenarios/save", json={
            "name": "x" * 101,
            "occupancy_change_pct": 0.0,
        })
    assert resp.status_code == 422


def test_save_scenario_invalid_params(client):
    """Parameters out of range should return 422."""
    with _patch_engine():
        resp = client.post("/api/scenarios/save", json={
            "name": "bad params",
            "occupancy_change_pct": 100.0,  # max is 50
        })
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/scenarios/saved
# ---------------------------------------------------------------------------


def test_list_saved_scenarios(client, db):
    """Listing should return saved scenarios without full results."""
    # Seed a scenario directly in the DB
    saved = SavedScenario(
        name="List test",
        occupancy_change_pct=0.0,
        adr_change_pct=0.0,
        foreign_ratio_change_pct=0.0,
        horizon=12,
        result_json=json.dumps({
            "baseline_forecast": [],
            "scenario_forecast": [],
            "impact_summary": {},
            "params": {},
        }),
    )
    db.add(saved)
    db.commit()

    resp = client.get("/api/scenarios/saved")
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) >= 1
    # Summaries should NOT include full result
    for s in data["scenarios"]:
        assert "result" not in s
        assert "id" in s
        assert "name" in s


# ---------------------------------------------------------------------------
# GET /api/scenarios/saved/{scenario_id}
# ---------------------------------------------------------------------------


def test_get_saved_scenario(client, db):
    """Getting a saved scenario by ID should return the full result."""
    saved = SavedScenario(
        name="Get test",
        occupancy_change_pct=3.0,
        adr_change_pct=-1.0,
        foreign_ratio_change_pct=0.0,
        horizon=6,
        result_json=json.dumps({
            "baseline_forecast": [{"period": "2026-01", "value": 400000}],
            "scenario_forecast": [{"period": "2026-01", "value": 410000}],
            "impact_summary": {"avg_baseline": 400000, "avg_scenario": 410000, "avg_change_pct": 2.5},
            "params": {"occupancy_change_pct": 3.0, "adr_change_pct": -1.0, "foreign_ratio_change_pct": 0.0},
        }),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    resp = client.get(f"/api/scenarios/saved/{saved.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Get test"
    assert "result" in data
    assert len(data["result"]["baseline_forecast"]) == 1


def test_get_saved_scenario_not_found(client):
    """Getting a non-existent scenario should return 404."""
    resp = client.get("/api/scenarios/saved/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/scenarios/saved/{scenario_id}
# ---------------------------------------------------------------------------


def test_delete_saved_scenario(client, db):
    """Deleting a saved scenario should remove it."""
    saved = SavedScenario(
        name="Delete test",
        occupancy_change_pct=0.0,
        adr_change_pct=0.0,
        foreign_ratio_change_pct=0.0,
        horizon=12,
        result_json=json.dumps({
            "baseline_forecast": [],
            "scenario_forecast": [],
            "impact_summary": {},
            "params": {},
        }),
    )
    db.add(saved)
    db.commit()
    db.refresh(saved)

    resp = client.delete(f"/api/scenarios/saved/{saved.id}")
    assert resp.status_code == 204

    # Confirm it's gone
    resp2 = client.get(f"/api/scenarios/saved/{saved.id}")
    assert resp2.status_code == 404


def test_delete_saved_scenario_not_found(client):
    """Deleting a non-existent scenario should return 404."""
    resp = client.delete("/api/scenarios/saved/99999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/scenarios/compare
# ---------------------------------------------------------------------------


def test_compare_scenarios(client, db):
    """Comparing scenarios should return full results keyed by ID."""
    scenarios = []
    for i in range(2):
        saved = SavedScenario(
            name=f"Compare test {i}",
            occupancy_change_pct=float(i),
            adr_change_pct=0.0,
            foreign_ratio_change_pct=0.0,
            horizon=6,
            result_json=json.dumps({
                "baseline_forecast": [{"period": "2026-01", "value": 400000 + i * 10000}],
                "scenario_forecast": [{"period": "2026-01", "value": 410000 + i * 10000}],
                "impact_summary": {"avg_baseline": 400000, "avg_scenario": 410000, "avg_change_pct": 2.5},
                "params": {"occupancy_change_pct": float(i), "adr_change_pct": 0.0, "foreign_ratio_change_pct": 0.0},
            }),
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        scenarios.append(saved)

    ids = [s.id for s in scenarios]
    resp = client.post("/api/scenarios/compare", json={"scenario_ids": ids})
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert len(data["scenarios"]) == 2
    for sid in ids:
        assert str(sid) in data["scenarios"]


def test_compare_scenarios_not_found(client):
    """Comparing with a non-existent ID should return 404."""
    resp = client.post("/api/scenarios/compare", json={"scenario_ids": [99998, 99999]})
    assert resp.status_code == 404


def test_compare_scenarios_too_many(client):
    """Requesting more than 3 scenarios should return 422."""
    resp = client.post("/api/scenarios/compare", json={"scenario_ids": [1, 2, 3, 4]})
    assert resp.status_code == 422


def test_compare_scenarios_empty(client):
    """Empty scenario_ids should return 422."""
    resp = client.post("/api/scenarios/compare", json={"scenario_ids": []})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/scenarios/feature-importance
# ---------------------------------------------------------------------------


def test_feature_importance(client):
    """Feature importance endpoint should return feature name to score mapping."""
    with _patch_engine():
        resp = client.get("/api/scenarios/feature-importance")
    assert resp.status_code == 200
    data = resp.json()
    assert "importances" in data
    importances = data["importances"]
    assert len(importances) > 0
    # All values should be non-negative floats
    for name, value in importances.items():
        assert isinstance(name, str)
        assert isinstance(value, float)
        assert value >= 0.0
