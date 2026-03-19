"""Tests for the trainer module (train_all, _store_predictions, retraining logic).

Covers:
- _store_predictions versioning and correctness
- _store_metrics persistence
- ModelTrainer.train_all orchestration (mocked sub-trainers)
- retrain_if_needed with force flag
- Data hash change detection triggering retraining
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
from sqlalchemy import text

from app.db.models import ModelMetric, Prediction, TrainingRun
from app.models.trainer import (
    ModelTrainer,
    _get_data_hash,
    _store_metrics,
    _store_predictions,
    needs_retraining,
    retrain_if_needed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_forecast(periods, values):
    """Create a mock ForecastResult with matching CI arrays."""
    fc = MagicMock()
    fc.periods = periods
    fc.values = np.array(values, dtype=float)
    fc.ci_lower_80 = fc.values * 0.92
    fc.ci_upper_80 = fc.values * 1.08
    fc.ci_lower_95 = fc.values * 0.85
    fc.ci_upper_95 = fc.values * 1.15
    return fc


def _cleanup_test_predictions(db, model_name):
    """Remove test predictions to avoid cross-test contamination."""
    db.execute(text("DELETE FROM predictions WHERE model = :m"), {"m": model_name})
    db.commit()


# ---------------------------------------------------------------------------
# _store_predictions: basic insertion
# ---------------------------------------------------------------------------

def test_store_predictions_inserts_correct_count(db):
    """_store_predictions should insert one row per forecast period."""
    model = "trainer_test_insert"
    fc = _make_forecast(["2028-01", "2028-02", "2028-03"], [100, 200, 300])
    try:
        count = _store_predictions(db, model, "turistas", "ES709", fc)
        db.commit()
        assert count == 3
        rows = db.query(Prediction).filter(Prediction.model == model).all()
        assert len(rows) == 3
    finally:
        _cleanup_test_predictions(db, model)


def test_store_predictions_first_version_is_one(db):
    """First call to _store_predictions should create version 1."""
    model = "trainer_test_v1"
    fc = _make_forecast(["2028-01"], [500])
    try:
        _store_predictions(db, model, "turistas", "ES709", fc)
        db.commit()
        row = db.query(Prediction).filter(Prediction.model == model).first()
        assert row.version == 1
        assert row.is_current is True
    finally:
        _cleanup_test_predictions(db, model)


def test_store_predictions_values_match_forecast(db):
    """Stored prediction values and CIs should match the input forecast."""
    model = "trainer_test_vals"
    fc = _make_forecast(["2028-06"], [1000.0])
    try:
        _store_predictions(db, model, "turistas", "ES709", fc)
        db.commit()
        row = db.query(Prediction).filter(Prediction.model == model).first()
        assert row.value_predicted == 1000.0
        assert abs(row.ci_lower_80 - 920.0) < 0.01
        assert abs(row.ci_upper_80 - 1080.0) < 0.01
        assert abs(row.ci_lower_95 - 850.0) < 0.01
        assert abs(row.ci_upper_95 - 1150.0) < 0.01
    finally:
        _cleanup_test_predictions(db, model)


# ---------------------------------------------------------------------------
# _store_predictions: versioning on re-store
# ---------------------------------------------------------------------------

def test_store_predictions_second_call_increments_version(db):
    """A second call to _store_predictions should create version 2."""
    model = "trainer_test_v2"
    fc = _make_forecast(["2028-01"], [100])
    try:
        _store_predictions(db, model, "ind", "GEO", fc)
        db.commit()
        fc2 = _make_forecast(["2028-01"], [200])
        _store_predictions(db, model, "ind", "GEO", fc2)
        db.commit()

        v2 = db.query(Prediction).filter(
            Prediction.model == model, Prediction.version == 2
        ).all()
        assert len(v2) == 1
        assert v2[0].value_predicted == 200.0
    finally:
        _cleanup_test_predictions(db, model)


def test_store_predictions_marks_old_version_non_current(db):
    """After re-storing, old version rows should have is_current=False."""
    model = "trainer_test_old"
    fc = _make_forecast(["2028-01", "2028-02"], [100, 200])
    try:
        _store_predictions(db, model, "ind", "GEO", fc)
        db.commit()
        fc2 = _make_forecast(["2028-01", "2028-02"], [300, 400])
        _store_predictions(db, model, "ind", "GEO", fc2)
        db.commit()

        old = db.query(Prediction).filter(
            Prediction.model == model, Prediction.version == 1
        ).all()
        assert all(r.is_current is False for r in old)

        current = db.query(Prediction).filter(
            Prediction.model == model, Prediction.version == 2
        ).all()
        assert all(r.is_current is True for r in current)
    finally:
        _cleanup_test_predictions(db, model)


def test_store_predictions_three_versions(db):
    """Three successive stores should produce versions 1, 2, 3."""
    model = "trainer_test_3v"
    try:
        for i in range(1, 4):
            fc = _make_forecast(["2028-01"], [i * 100])
            _store_predictions(db, model, "ind", "GEO", fc)
            db.commit()

        total = db.query(Prediction).filter(Prediction.model == model).count()
        assert total == 3  # one row per version

        current = db.query(Prediction).filter(
            Prediction.model == model, Prediction.is_current == True  # noqa: E712
        ).all()
        assert len(current) == 1
        assert current[0].version == 3
        assert current[0].value_predicted == 300.0
    finally:
        _cleanup_test_predictions(db, model)


def test_store_predictions_sets_trained_at(db):
    """Each stored prediction should have a non-null trained_at timestamp."""
    model = "trainer_test_ts"
    fc = _make_forecast(["2028-01"], [100])
    try:
        _store_predictions(db, model, "ind", "GEO", fc)
        db.commit()
        row = db.query(Prediction).filter(Prediction.model == model).first()
        assert row.trained_at is not None
    finally:
        _cleanup_test_predictions(db, model)


# ---------------------------------------------------------------------------
# _store_metrics
# ---------------------------------------------------------------------------

def test_store_metrics_persists_values(db):
    """_store_metrics should insert metrics rows for each model."""
    from app.models.forecaster import ModelMetrics

    metrics = {
        "test_m1": ModelMetrics(rmse=100.0, mae=80.0, mape=5.5),
        "test_m2": ModelMetrics(rmse=120.0, mae=90.0, mape=6.0),
    }
    try:
        _store_metrics(db, metrics, "test_ind", "TEST_GEO", test_size=12)
        db.commit()

        row1 = db.query(ModelMetric).filter(
            ModelMetric.model == "test_m1",
            ModelMetric.indicator == "test_ind",
        ).first()
        assert row1 is not None
        assert row1.rmse == 100.0
        assert row1.mape == 5.5
        assert row1.test_size == 12

        row2 = db.query(ModelMetric).filter(
            ModelMetric.model == "test_m2",
            ModelMetric.indicator == "test_ind",
        ).first()
        assert row2 is not None
        assert row2.mae == 90.0
    finally:
        db.execute(text("DELETE FROM model_metrics WHERE indicator = 'test_ind'"))
        db.commit()


def test_store_metrics_ignores_non_model_metrics(db):
    """_store_metrics should skip dict entries that are not ModelMetrics instances."""
    from app.models.forecaster import ModelMetrics

    metrics = {
        "valid": ModelMetrics(rmse=1.0, mae=1.0, mape=1.0),
        "invalid": "not a ModelMetrics object",
    }
    try:
        _store_metrics(db, metrics, "test_skip", "TEST_GEO", test_size=6)
        db.commit()

        count = db.query(ModelMetric).filter(
            ModelMetric.indicator == "test_skip"
        ).count()
        assert count == 1
    finally:
        db.execute(text("DELETE FROM model_metrics WHERE indicator = 'test_skip'"))
        db.commit()


# ---------------------------------------------------------------------------
# ModelTrainer.train_all (mocked sub-trainers)
# ---------------------------------------------------------------------------

@patch("app.models.trainer.train_scenario_engine")
@patch("app.models.trainer.train_profiler")
@patch("app.models.trainer.train_forecaster")
def test_train_all_calls_all_sub_trainers(mock_fc, mock_prof, mock_sc, db):
    """ModelTrainer.train_all should call all three training functions."""
    mock_fc.return_value = {"sarima": 12, "ensemble": 12}
    mock_prof.return_value = {"n_clusters": 4, "n_records": 100, "profiles": 4}
    mock_sc.return_value = {"status": "trained", "features": 5}

    trainer = ModelTrainer()
    result = trainer.train_all(db)

    mock_fc.assert_called_once_with(db)
    mock_prof.assert_called_once_with(db)
    mock_sc.assert_called_once_with(db)

    assert "forecaster" in result
    assert "profiler" in result
    assert "scenario_engine" in result


@patch("app.models.trainer.train_scenario_engine")
@patch("app.models.trainer.train_profiler")
@patch("app.models.trainer.train_forecaster")
def test_train_all_propagates_results(mock_fc, mock_prof, mock_sc, db):
    """train_all should return the combined results from all sub-trainers."""
    mock_fc.return_value = {"sarima": 6}
    mock_prof.return_value = {"n_clusters": 3}
    mock_sc.return_value = {"status": "trained"}

    trainer = ModelTrainer()
    result = trainer.train_all(db)

    assert result["forecaster"] == {"sarima": 6}
    assert result["profiler"] == {"n_clusters": 3}
    assert result["scenario_engine"] == {"status": "trained"}


# ---------------------------------------------------------------------------
# retrain_if_needed
# ---------------------------------------------------------------------------

@patch("app.models.trainer.ModelTrainer")
def test_retrain_if_needed_force_flag(mock_cls, db):
    """With force=True, retrain_if_needed should always train."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()

    # Seed a training run with current hash so normal check would say "no"
    current_hash = _get_data_hash(db)
    db.add(TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-12",
        data_hash=current_hash,
        models_trained=json.dumps(["sarima"]),
        status="success",
        duration_seconds=5.0,
    ))
    db.commit()
    assert needs_retraining(db) is False

    mock_trainer_instance = MagicMock()
    mock_cls.return_value = mock_trainer_instance

    result = retrain_if_needed(db, force=True)
    assert result["retrained"] is True
    mock_trainer_instance.train_all.assert_called_once_with(db)

    # Clean up
    db.execute(text("DELETE FROM training_runs"))
    db.commit()


@patch("app.models.trainer.ModelTrainer")
def test_retrain_if_needed_skips_when_up_to_date(mock_cls, db):
    """retrain_if_needed should skip training if data hash matches."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()

    current_hash = _get_data_hash(db)
    db.add(TrainingRun(
        trained_at="2026-01-01T00:00:00",
        data_up_to="2025-12",
        data_hash=current_hash,
        models_trained=json.dumps(["sarima"]),
        status="success",
        duration_seconds=5.0,
    ))
    db.commit()

    result = retrain_if_needed(db, force=False)
    assert result["retrained"] is False
    assert "No new data" in result["reason"]
    mock_cls.return_value.train_all.assert_not_called()

    # Clean up
    db.execute(text("DELETE FROM training_runs"))
    db.commit()


@patch("app.models.trainer.ModelTrainer")
def test_retrain_if_needed_records_error_on_failure(mock_cls, db):
    """If training fails, retrain_if_needed should record an error TrainingRun."""
    db.execute(text("DELETE FROM training_runs"))
    db.commit()

    mock_trainer_instance = MagicMock()
    mock_trainer_instance.train_all.side_effect = RuntimeError("boom")
    mock_cls.return_value = mock_trainer_instance

    result = retrain_if_needed(db, force=True)
    assert result["retrained"] is False
    assert "boom" in result["reason"]

    error_run = db.query(TrainingRun).filter(TrainingRun.status == "error").first()
    assert error_run is not None
    assert "boom" in error_run.error_message

    # Clean up
    db.execute(text("DELETE FROM training_runs"))
    db.commit()
