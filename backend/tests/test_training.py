"""Tests for model retraining detection, TrainingRun tracking, and new endpoints."""

import json

from sqlalchemy import text

from app.db.models import TrainingRun
from app.models.trainer import (
    _get_data_hash,
    _get_latest_data_period,
    _get_latest_training,
    needs_retraining,
)


# ---------------------------------------------------------------------------
# Unit tests for retraining detection helpers
# ---------------------------------------------------------------------------

def test_get_data_hash_returns_string(db):
    """Data hash should return a non-empty hex string."""
    h = _get_data_hash(db)
    assert isinstance(h, str)
    assert len(h) == 16


def test_get_data_hash_deterministic(db):
    """Calling data hash twice with the same data should return the same value."""
    h1 = _get_data_hash(db)
    h2 = _get_data_hash(db)
    assert h1 == h2


def test_get_latest_data_period(db):
    """Should return the latest fetched_at value from time_series."""
    result = _get_latest_data_period(db)
    assert result is not None


def test_get_latest_training_none_initially(db):
    """With no training runs in DB, should return None."""
    # Clean any training runs that may exist
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    result = _get_latest_training(db)
    assert result is None


def test_needs_retraining_true_when_no_training(db):
    """Should return True when no training has ever happened."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    assert needs_retraining(db) is True


def test_needs_retraining_false_after_training(db):
    """Should return False when a training run exists with the current data hash."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    current_hash = _get_data_hash(db)
    run = TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-12",
        data_hash=current_hash,
        models_trained=json.dumps(["sarima"]),
        status="success",
        duration_seconds=10.0,
    )
    db.add(run)
    db.commit()
    assert needs_retraining(db) is False


def test_needs_retraining_true_with_stale_hash(db):
    """Should return True when the data hash differs from the last training."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    run = TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-12",
        data_hash="old_stale_hash_00",
        models_trained=json.dumps(["sarima"]),
        status="success",
        duration_seconds=10.0,
    )
    db.add(run)
    db.commit()
    assert needs_retraining(db) is True


def test_needs_retraining_ignores_error_runs(db):
    """Error training runs should not prevent retraining."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    current_hash = _get_data_hash(db)
    run = TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-12",
        data_hash=current_hash,
        models_trained=json.dumps([]),
        status="error",
        error_message="Something went wrong",
        duration_seconds=1.0,
    )
    db.add(run)
    db.commit()
    # Only successful runs count
    assert needs_retraining(db) is True


# ---------------------------------------------------------------------------
# Integration tests for new API endpoints
# ---------------------------------------------------------------------------

def test_training_info_no_runs(client, db):
    """training-info should return no_training status when no runs exist."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    r = client.get("/api/predictions/training-info")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "no_training"
    assert data["trained_at"] is None
    assert data["models_trained"] == []


def test_training_info_with_run(client, db):
    """training-info should return latest training run details."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    run = TrainingRun(
        trained_at="2026-03-15T08:00:00",
        data_up_to="2025-12-31",
        data_hash="abcdef1234567890",
        models_trained=json.dumps(["sarima", "holt_winters", "ensemble"]),
        status="success",
        duration_seconds=45.3,
    )
    db.add(run)
    db.commit()

    r = client.get("/api/predictions/training-info")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["trained_at"] == "2026-03-15T08:00:00"
    assert data["data_up_to"] == "2025-12-31"
    assert "sarima" in data["models_trained"]
    assert data["duration_seconds"] == 45.3


def test_training_info_returns_latest(client, db):
    """training-info should return the most recent successful run."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    # Older run
    db.add(TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-06",
        data_hash="hash1",
        models_trained=json.dumps(["sarima"]),
        status="success",
        duration_seconds=10.0,
    ))
    # Newer run
    db.add(TrainingRun(
        trained_at="2026-03-01T00:00:00",
        data_up_to="2025-12",
        data_hash="hash2",
        models_trained=json.dumps(["sarima", "ensemble"]),
        status="success",
        duration_seconds=20.0,
    ))
    db.commit()

    r = client.get("/api/predictions/training-info")
    data = r.json()
    assert data["trained_at"] == "2026-03-01T00:00:00"
    assert data["data_up_to"] == "2025-12"


# ---------------------------------------------------------------------------
# TrainingRun ORM model tests
# ---------------------------------------------------------------------------

def test_training_run_model_fields(db):
    """TrainingRun should persist all fields correctly."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    run = TrainingRun(
        trained_at="2026-03-15T10:00:00",
        data_up_to="2026-02",
        data_hash="deadbeef12345678",
        models_trained=json.dumps(["sarima", "profiler"]),
        status="success",
        duration_seconds=33.7,
    )
    db.add(run)
    db.commit()

    saved = db.query(TrainingRun).first()
    assert saved is not None
    assert saved.trained_at == "2026-03-15T10:00:00"
    assert saved.data_up_to == "2026-02"
    assert saved.data_hash == "deadbeef12345678"
    assert saved.status == "success"
    assert saved.duration_seconds == 33.7
    assert json.loads(saved.models_trained) == ["sarima", "profiler"]
    assert saved.error_message is None


def test_training_run_error_fields(db):
    """TrainingRun should store error information correctly."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
    run = TrainingRun(
        trained_at="2026-03-15T10:00:00",
        data_up_to="2026-02",
        data_hash="deadbeef12345678",
        models_trained=json.dumps([]),
        status="error",
        error_message="SARIMA convergence failed",
        duration_seconds=5.2,
    )
    db.add(run)
    db.commit()

    saved = db.query(TrainingRun).first()
    assert saved.status == "error"
    assert saved.error_message == "SARIMA convergence failed"
