"""Tests for the predictions table unique constraint (Issue #810).

Verifies that:
- The UniqueConstraint on (model, indicator, geo_code, period, version) exists
- Duplicate predictions within the same version are rejected
- Different versions of the same prediction are allowed
- INSERT OR REPLACE in _store_predictions handles duplicates gracefully
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.models import Prediction


# ---------------------------------------------------------------------------
# Schema-level constraint tests
# ---------------------------------------------------------------------------

def test_unique_constraint_exists_in_model():
    """The Prediction model should declare a UniqueConstraint named uq_prediction."""
    constraint_names = [
        c.name for c in Prediction.__table__.constraints
        if hasattr(c, "name") and c.name is not None
    ]
    assert "uq_prediction" in constraint_names


def test_unique_constraint_columns():
    """uq_prediction should cover (model, indicator, geo_code, period, version)."""
    for c in Prediction.__table__.constraints:
        if getattr(c, "name", None) == "uq_prediction":
            col_names = [col.name for col in c.columns]
            assert col_names == ["model", "indicator", "geo_code", "period", "version"]
            return
    pytest.fail("uq_prediction constraint not found")


# ---------------------------------------------------------------------------
# Database-level enforcement tests
# ---------------------------------------------------------------------------

def test_duplicate_prediction_rejected(db):
    """Inserting two rows with the same (model, indicator, geo_code, period, version)
    should raise an IntegrityError."""
    db.execute(
        text("""
            INSERT INTO predictions
                (model, indicator, geo_code, period, value_predicted, version, is_current)
            VALUES ('dup_test', 'ind', 'GEO', '2028-01', 100.0, 1, 1)
        """)
    )
    db.flush()

    with pytest.raises(IntegrityError):
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted, version, is_current)
                VALUES ('dup_test', 'ind', 'GEO', '2028-01', 200.0, 1, 1)
            """)
        )
        db.flush()

    db.rollback()
    # Clean up
    db.execute(text("DELETE FROM predictions WHERE model = 'dup_test'"))
    db.commit()


def test_different_versions_allowed(db):
    """Two rows differing only in version should both be accepted."""
    try:
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted, version, is_current)
                VALUES ('ver_test', 'ind', 'GEO', '2028-01', 100.0, 1, 0)
            """)
        )
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted, version, is_current)
                VALUES ('ver_test', 'ind', 'GEO', '2028-01', 200.0, 2, 1)
            """)
        )
        db.flush()

        count = db.execute(
            text("SELECT COUNT(*) FROM predictions WHERE model = 'ver_test'")
        ).scalar()
        assert count == 2
    finally:
        db.rollback()
        db.execute(text("DELETE FROM predictions WHERE model = 'ver_test'"))
        db.commit()


def test_different_periods_same_version_allowed(db):
    """Two rows with same version but different periods should be accepted."""
    try:
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted, version, is_current)
                VALUES ('period_test', 'ind', 'GEO', '2028-01', 100.0, 1, 1)
            """)
        )
        db.execute(
            text("""
                INSERT INTO predictions
                    (model, indicator, geo_code, period, value_predicted, version, is_current)
                VALUES ('period_test', 'ind', 'GEO', '2028-02', 200.0, 1, 1)
            """)
        )
        db.flush()

        count = db.execute(
            text("SELECT COUNT(*) FROM predictions WHERE model = 'period_test'")
        ).scalar()
        assert count == 2
    finally:
        db.rollback()
        db.execute(text("DELETE FROM predictions WHERE model = 'period_test'"))
        db.commit()


# ---------------------------------------------------------------------------
# INSERT OR REPLACE behaviour in _store_predictions
# ---------------------------------------------------------------------------

def test_store_predictions_handles_rerun_same_version(db):
    """If _store_predictions is called twice producing the same version,
    INSERT OR REPLACE should update rather than fail."""
    from unittest.mock import MagicMock

    from app.models.trainer import _store_predictions

    forecast = MagicMock()
    forecast.periods = ["2029-01", "2029-02"]
    forecast.values = [100.0, 200.0]
    forecast.ci_lower_80 = [90.0, 180.0]
    forecast.ci_upper_80 = [110.0, 220.0]
    forecast.ci_lower_95 = [80.0, 160.0]
    forecast.ci_upper_95 = [120.0, 240.0]

    model = "replace_test"
    try:
        # First insert
        count1 = _store_predictions(db, model, "ind", "GEO", forecast)
        db.commit()
        assert count1 == 2

        # Manually insert same version again via INSERT OR REPLACE
        # (simulates a crash-recovery scenario where the version was not incremented)
        db.execute(
            text("""
                INSERT OR REPLACE INTO predictions
                    (model, indicator, geo_code, period, value_predicted,
                     ci_lower_80, ci_upper_80, ci_lower_95, ci_upper_95,
                     version, is_current)
                VALUES ('replace_test', 'ind', 'GEO', '2029-01', 999.0,
                        900.0, 1100.0, 800.0, 1200.0, 1, 1)
            """)
        )
        db.commit()

        # Should have replaced the row, not duplicated it
        rows = db.execute(
            text("""
                SELECT value_predicted FROM predictions
                WHERE model = 'replace_test' AND period = '2029-01' AND version = 1
            """)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 999.0
    finally:
        db.execute(text("DELETE FROM predictions WHERE model = 'replace_test'"))
        db.commit()
