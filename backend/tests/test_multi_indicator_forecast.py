"""Tests for multi-indicator forecasting (issue #1011).

Covers:
- load_arrivals_series with custom indicator parameter
- get_forecastable_indicators returns indicators with sufficient data
- train_forecaster iterates over multiple indicators
- _train_single_indicator trains and stores per-indicator predictions
- Predictions endpoint returns data for non-turistas indicators
"""

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.db.models import ModelMetric, Prediction
from app.utils.queries import get_forecastable_indicators, load_arrivals_series


# ---------------------------------------------------------------------------
# load_arrivals_series: parameterized indicator
# ---------------------------------------------------------------------------

def test_load_arrivals_series_default_is_turistas(db):
    """load_arrivals_series with no indicator arg should return turistas data."""
    series = load_arrivals_series(db)
    assert series.name == "turistas"
    assert len(series) > 0


def test_load_arrivals_series_custom_indicator(db):
    """load_arrivals_series should load data for a non-default indicator."""
    series = load_arrivals_series(db, indicator="turistas_extranjeros")
    assert series.name == "turistas_extranjeros"
    assert len(series) > 0
    assert isinstance(series.index, pd.PeriodIndex)


def test_load_arrivals_series_nonexistent_indicator(db):
    """load_arrivals_series for a nonexistent indicator should return empty series."""
    series = load_arrivals_series(db, indicator="does_not_exist")
    assert len(series) == 0


def test_load_arrivals_series_custom_geo_code(db):
    """load_arrivals_series should respect the geo_code parameter."""
    series = load_arrivals_series(db, indicator="turistas", geo_code="INVALID")
    assert len(series) == 0


# ---------------------------------------------------------------------------
# get_forecastable_indicators
# ---------------------------------------------------------------------------

def test_get_forecastable_indicators_returns_list(db):
    """get_forecastable_indicators should return a non-empty list of strings."""
    indicators = get_forecastable_indicators(db)
    assert isinstance(indicators, list)
    assert len(indicators) > 0
    assert all(isinstance(i, str) for i in indicators)


def test_get_forecastable_indicators_includes_turistas(db):
    """turistas should be among forecastable indicators (has 72 monthly obs)."""
    indicators = get_forecastable_indicators(db)
    assert "turistas" in indicators


def test_get_forecastable_indicators_includes_turistas_extranjeros(db):
    """turistas_extranjeros should be forecastable (has 72 monthly obs in test data)."""
    indicators = get_forecastable_indicators(db)
    assert "turistas_extranjeros" in indicators


def test_get_forecastable_indicators_respects_min_observations(db):
    """With a very high min_observations, most indicators should be excluded."""
    indicators = get_forecastable_indicators(db, min_observations=1000)
    assert len(indicators) == 0


def test_get_forecastable_indicators_low_threshold(db):
    """With a low threshold, more indicators should be included."""
    indicators_low = get_forecastable_indicators(db, min_observations=12)
    indicators_high = get_forecastable_indicators(db, min_observations=60)
    assert len(indicators_low) >= len(indicators_high)


# ---------------------------------------------------------------------------
# _train_single_indicator
# ---------------------------------------------------------------------------

@patch("app.models.trainer.Forecaster")
@patch("app.models.trainer.load_arrivals_series")
def test_train_single_indicator_stores_predictions(mock_load, mock_forecaster_cls, db):
    """_train_single_indicator should store predictions for the given indicator."""
    from app.models.trainer import _train_single_indicator

    # Mock load_arrivals_series to return a fake series
    periods = pd.period_range("2020-01", periods=72, freq="M")
    mock_load.return_value = pd.Series(
        np.random.default_rng(42).integers(100, 500, size=72).astype(float),
        index=periods, name="test_single_train",
    )

    # Set up mock forecaster
    mock_forecaster = MagicMock()
    mock_forecaster_cls.return_value = mock_forecaster

    # Mock evaluate to return empty metrics
    mock_forecaster.evaluate.return_value = {}

    # Mock prediction methods
    mock_fc = MagicMock()
    mock_fc.periods = ["2028-01", "2028-02"]
    mock_fc.values = np.array([100.0, 200.0])
    mock_fc.ci_lower_80 = np.array([90.0, 180.0])
    mock_fc.ci_upper_80 = np.array([110.0, 220.0])
    mock_fc.ci_lower_95 = np.array([85.0, 170.0])
    mock_fc.ci_upper_95 = np.array([115.0, 230.0])

    mock_forecaster.predict_sarima.return_value = mock_fc
    mock_forecaster.predict_hw.return_value = mock_fc
    mock_forecaster.predict_naive.return_value = mock_fc
    mock_forecaster.predict.return_value = mock_fc

    test_indicator = "test_single_train"
    try:
        result = _train_single_indicator(db, test_indicator, "ES709", 2)
        db.commit()

        assert "sarima" in result
        assert "ensemble" in result
        assert result["sarima"] == 2
        assert result["ensemble"] == 2

        # Verify predictions exist in DB
        preds = db.query(Prediction).filter(
            Prediction.indicator == test_indicator
        ).all()
        assert len(preds) == 8  # 4 models x 2 periods
    finally:
        db.execute(text("DELETE FROM predictions WHERE indicator = :i"),
                   {"i": test_indicator})
        db.execute(text("DELETE FROM model_metrics WHERE indicator = :i"),
                   {"i": test_indicator})
        db.commit()


# ---------------------------------------------------------------------------
# train_forecaster: multi-indicator
# ---------------------------------------------------------------------------

@patch("app.models.trainer._train_single_indicator")
@patch("app.models.trainer.get_forecastable_indicators")
def test_train_forecaster_iterates_all_indicators(mock_get_ind, mock_train, db):
    """train_forecaster should call _train_single_indicator for each indicator."""
    from app.models.trainer import train_forecaster

    mock_get_ind.return_value = ["turistas", "turistas_extranjeros", "alojatur_ocupacion"]
    mock_train.return_value = {"sarima": 12, "ensemble": 12}

    with patch("app.models.trainer.Forecaster") as mock_fc_cls, \
         patch("app.models.trainer.joblib"):
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc

        result = train_forecaster(db, horizon=12)

    assert len(result) == 3
    assert "turistas" in result
    assert "turistas_extranjeros" in result
    assert "alojatur_ocupacion" in result
    assert mock_train.call_count == 3


@patch("app.models.trainer._train_single_indicator")
@patch("app.models.trainer.get_forecastable_indicators")
def test_train_forecaster_skips_failed_indicator(mock_get_ind, mock_train, db):
    """If one indicator fails, train_forecaster should continue with others."""
    from app.models.trainer import train_forecaster

    mock_get_ind.return_value = ["turistas", "bad_indicator"]
    mock_train.side_effect = [
        {"sarima": 12, "ensemble": 12},
        RuntimeError("insufficient data"),
    ]

    with patch("app.models.trainer.Forecaster") as mock_fc_cls, \
         patch("app.models.trainer.joblib"):
        mock_fc = MagicMock()
        mock_fc_cls.return_value = mock_fc

        result = train_forecaster(db, horizon=12)

    assert result["turistas"] == {"sarima": 12, "ensemble": 12}
    assert result["bad_indicator"] == {"status": "error"}


@patch("app.models.trainer._train_single_indicator")
@patch("app.models.trainer.get_forecastable_indicators")
def test_train_forecaster_empty_indicators(mock_get_ind, mock_train, db):
    """train_forecaster should return empty dict when no indicators are available."""
    from app.models.trainer import train_forecaster

    mock_get_ind.return_value = []

    result = train_forecaster(db, horizon=12)
    assert result == {}
    mock_train.assert_not_called()


# ---------------------------------------------------------------------------
# Predictions endpoint: multi-indicator
# ---------------------------------------------------------------------------

def test_predictions_endpoint_turistas_default(client):
    """GET /api/predictions with default params should return turistas forecasts."""
    resp = client.get("/api/predictions")
    assert resp.status_code == 200
    data = resp.json()
    assert "forecast" in data
    assert len(data["forecast"]) > 0


def test_predictions_endpoint_custom_indicator(client, db):
    """GET /api/predictions with a custom indicator should return its predictions."""
    # Seed predictions for a test indicator
    test_ind = "alojatur_ocupacion"
    for i in range(1, 4):
        db.add(Prediction(
            model="ensemble",
            indicator=test_ind,
            geo_code="ES709",
            period=f"2028-{i:02d}",
            value_predicted=70.0 + i,
            ci_lower_80=65.0,
            ci_upper_80=75.0,
            ci_lower_95=60.0,
            ci_upper_95=80.0,
        ))
    db.commit()

    try:
        resp = client.get(f"/api/predictions?indicator={test_ind}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["forecast"]) == 3
        assert data["forecast"][0]["value"] == 71.0
    finally:
        db.execute(text("DELETE FROM predictions WHERE indicator = :i AND period LIKE '2028-%'"),
                   {"i": test_ind})
        db.commit()


def test_predictions_compare_custom_indicator(client, db):
    """GET /api/predictions/compare should work for non-turistas indicators."""
    test_ind = "test_compare_ind"
    for model_name in ["sarima", "ensemble"]:
        db.add(Prediction(
            model=model_name,
            indicator=test_ind,
            geo_code="ES709",
            period="2028-01",
            value_predicted=100.0,
            ci_lower_80=90.0,
            ci_upper_80=110.0,
            ci_lower_95=85.0,
            ci_upper_95=115.0,
        ))
    db.commit()

    try:
        resp = client.get(f"/api/predictions/compare?indicator={test_ind}")
        assert resp.status_code == 200
        data = resp.json()
        assert "sarima" in data["models"]
        assert "ensemble" in data["models"]
    finally:
        db.execute(text("DELETE FROM predictions WHERE indicator = :i"),
                   {"i": test_ind})
        db.commit()
