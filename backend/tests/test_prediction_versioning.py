"""Tests for prediction versioning and history (Issue #193)."""

from sqlalchemy import text

from app.db.models import Prediction


# ---------------------------------------------------------------------------
# Model column tests
# ---------------------------------------------------------------------------

def test_prediction_has_versioning_columns(db):
    """Prediction model should have trained_at, version, and is_current columns."""
    pred = db.query(Prediction).first()
    assert pred is not None
    assert hasattr(pred, "trained_at")
    assert hasattr(pred, "version")
    assert hasattr(pred, "is_current")


def test_prediction_default_values(db):
    """New predictions should default to version=1, is_current=True."""
    pred = Prediction(
        model="test_model",
        indicator="test_ind",
        geo_code="TEST",
        period="2026-01",
        value_predicted=100.0,
    )
    db.add(pred)
    db.flush()

    saved = (
        db.query(Prediction)
        .filter(Prediction.model == "test_model")
        .first()
    )
    assert saved is not None
    assert saved.version == 1
    assert saved.is_current is True

    # Clean up
    db.rollback()


def test_seed_predictions_are_current(db):
    """All seed predictions should have is_current=True."""
    count_all = (
        db.query(Prediction)
        .filter(Prediction.model == "ensemble")
        .count()
    )
    count_current = (
        db.query(Prediction)
        .filter(
            Prediction.model == "ensemble",
            Prediction.is_current == True,  # noqa: E712
        )
        .count()
    )
    assert count_all > 0
    assert count_current == count_all


# ---------------------------------------------------------------------------
# API endpoint tests: existing behavior preserved
# ---------------------------------------------------------------------------

def test_predictions_endpoint_returns_only_current(client, db):
    """GET /predictions should only return current predictions."""
    # Insert a non-current prediction
    db.execute(
        text("""
            INSERT INTO predictions
                (model, indicator, geo_code, period, value_predicted,
                 version, is_current)
            VALUES ('ensemble', 'turistas', 'ES709', '2026-01',
                    999999.0, 0, 0)
        """)
    )
    db.commit()

    r = client.get("/api/predictions?indicator=turistas&model=ensemble&horizon=12")
    assert r.status_code == 200
    data = r.json()

    # The superseded prediction (value=999999) should NOT appear
    values = [p["value"] for p in data["forecast"]]
    assert 999999.0 not in values

    # Clean up the non-current prediction
    db.execute(
        text("DELETE FROM predictions WHERE version = 0 AND is_current = 0")
    )
    db.commit()


def test_compare_endpoint_returns_only_current(client, db):
    """GET /predictions/compare should only return current predictions."""
    # Insert a non-current prediction for sarima
    db.execute(
        text("""
            INSERT INTO predictions
                (model, indicator, geo_code, period, value_predicted,
                 version, is_current)
            VALUES ('sarima', 'turistas', 'ES709', '2026-01',
                    888888.0, 0, 0)
        """)
    )
    db.commit()

    r = client.get("/api/predictions/compare?indicator=turistas")
    assert r.status_code == 200
    data = r.json()

    sarima_values = [p["value"] for p in data["models"]["sarima"]]
    assert 888888.0 not in sarima_values

    # Clean up
    db.execute(
        text("DELETE FROM predictions WHERE version = 0 AND is_current = 0")
    )
    db.commit()


# ---------------------------------------------------------------------------
# History endpoint tests
# ---------------------------------------------------------------------------

def test_history_endpoint_returns_200(client):
    """GET /predictions/history should return 200."""
    r = client.get("/api/predictions/history?model=ensemble")
    assert r.status_code == 200


def test_history_endpoint_response_structure(client):
    """History endpoint should return correct structure."""
    r = client.get("/api/predictions/history?model=ensemble")
    assert r.status_code == 200
    data = r.json()

    assert "model" in data
    assert data["model"] == "ensemble"
    assert "indicator" in data
    assert "geo_code" in data
    assert "total_versions" in data
    assert "versions" in data
    assert isinstance(data["versions"], list)


def test_history_endpoint_includes_current_version(client):
    """History should include at least the current version."""
    r = client.get("/api/predictions/history?model=ensemble")
    data = r.json()
    assert data["total_versions"] >= 1

    # At least one version should be current
    current_versions = [v for v in data["versions"] if v["is_current"]]
    assert len(current_versions) >= 1


def test_history_endpoint_version_has_forecast(client):
    """Each version in history should contain forecast points."""
    r = client.get("/api/predictions/history?model=ensemble")
    data = r.json()

    for version in data["versions"]:
        assert "version" in version
        assert "trained_at" in version
        assert "is_current" in version
        assert "forecast" in version
        assert isinstance(version["forecast"], list)
        assert len(version["forecast"]) > 0

        # Each forecast point should have the standard fields
        point = version["forecast"][0]
        assert "period" in point
        assert "value" in point
        assert "ci_available" in point


def test_history_endpoint_limit_parameter(client, db):
    """History limit parameter should control how many versions are returned."""
    # Insert a second version of predictions (non-current)
    for i in range(1, 13):
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted,
                     ci_lower_80, ci_upper_80, ci_lower_95, ci_upper_95,
                     version, is_current)
                VALUES ('ensemble', 'turistas', 'ES709', :period,
                        :value, :lo80, :hi80, :lo95, :hi95,
                        99, 0)
            """),
            {
                "period": f"2026-{i:02d}",
                "value": 400000 + i * 5000,
                "lo80": (400000 + i * 5000) * 0.92,
                "hi80": (400000 + i * 5000) * 1.08,
                "lo95": (400000 + i * 5000) * 0.85,
                "hi95": (400000 + i * 5000) * 1.15,
            },
        )
    db.commit()

    # Request with limit=1 should return only the latest version
    r = client.get("/api/predictions/history?model=ensemble&limit=1")
    data = r.json()
    assert data["total_versions"] == 1

    # Request with limit=5 should return both versions
    r = client.get("/api/predictions/history?model=ensemble&limit=5")
    data = r.json()
    assert data["total_versions"] == 2

    # Clean up
    db.execute(
        text("DELETE FROM predictions WHERE version = 99")
    )
    db.commit()


def test_history_endpoint_nonexistent_model(client):
    """History for a nonexistent model should return empty versions list."""
    r = client.get("/api/predictions/history?model=nonexistent_model_xyz")
    assert r.status_code == 200
    data = r.json()
    assert data["total_versions"] == 0
    assert data["versions"] == []


def test_history_endpoint_limit_validation(client):
    """History limit outside valid range should return 422."""
    r = client.get("/api/predictions/history?model=ensemble&limit=0")
    assert r.status_code == 422

    r = client.get("/api/predictions/history?model=ensemble&limit=21")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# _store_predictions versioning logic tests
# ---------------------------------------------------------------------------

def test_store_predictions_versioning(db):
    """_store_predictions should increment version and mark old as superseded."""
    from unittest.mock import MagicMock

    from app.models.trainer import _store_predictions

    # Create a mock forecast object
    forecast = MagicMock()
    forecast.periods = ["2027-01", "2027-02", "2027-03"]
    forecast.values = [100.0, 200.0, 300.0]
    forecast.ci_lower_80 = [90.0, 180.0, 270.0]
    forecast.ci_upper_80 = [110.0, 220.0, 330.0]
    forecast.ci_lower_95 = [80.0, 160.0, 240.0]
    forecast.ci_upper_95 = [120.0, 240.0, 360.0]

    # First call: should create version 1
    count1 = _store_predictions(db, "test_versioning", "test_ind", "TEST", forecast)
    db.commit()
    assert count1 == 3

    v1_rows = (
        db.query(Prediction)
        .filter(
            Prediction.model == "test_versioning",
            Prediction.version == 1,
        )
        .all()
    )
    assert len(v1_rows) == 3
    assert all(r.is_current is True for r in v1_rows)

    # Second call: should create version 2 and mark version 1 as non-current
    forecast.values = [150.0, 250.0, 350.0]
    forecast.ci_lower_80 = [135.0, 225.0, 315.0]
    forecast.ci_upper_80 = [165.0, 275.0, 385.0]
    forecast.ci_lower_95 = [120.0, 200.0, 280.0]
    forecast.ci_upper_95 = [180.0, 300.0, 420.0]

    count2 = _store_predictions(db, "test_versioning", "test_ind", "TEST", forecast)
    db.commit()
    assert count2 == 3

    # Version 1 should now be non-current
    v1_rows = (
        db.query(Prediction)
        .filter(
            Prediction.model == "test_versioning",
            Prediction.version == 1,
        )
        .all()
    )
    assert len(v1_rows) == 3
    assert all(r.is_current is False for r in v1_rows)

    # Version 2 should be current
    v2_rows = (
        db.query(Prediction)
        .filter(
            Prediction.model == "test_versioning",
            Prediction.version == 2,
        )
        .all()
    )
    assert len(v2_rows) == 3
    assert all(r.is_current is True for r in v2_rows)

    # Total predictions should be 6 (3 from each version)
    total = (
        db.query(Prediction)
        .filter(Prediction.model == "test_versioning")
        .count()
    )
    assert total == 6

    # Clean up
    db.execute(text("DELETE FROM predictions WHERE model = 'test_versioning'"))
    db.commit()


def test_store_predictions_trained_at_populated(db):
    """_store_predictions should set trained_at on new predictions."""
    from unittest.mock import MagicMock

    from app.models.trainer import _store_predictions

    forecast = MagicMock()
    forecast.periods = ["2027-06"]
    forecast.values = [500.0]
    forecast.ci_lower_80 = [450.0]
    forecast.ci_upper_80 = [550.0]
    forecast.ci_lower_95 = [400.0]
    forecast.ci_upper_95 = [600.0]

    _store_predictions(db, "test_trained_at", "test_ind", "TEST", forecast)
    db.commit()

    row = (
        db.query(Prediction)
        .filter(Prediction.model == "test_trained_at")
        .first()
    )
    assert row is not None
    assert row.trained_at is not None

    # Clean up
    db.execute(text("DELETE FROM predictions WHERE model = 'test_trained_at'"))
    db.commit()
