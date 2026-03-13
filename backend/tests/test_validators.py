"""Tests for data validation logic and data quality checks."""

import json

from sqlalchemy import text


def test_timeseries_no_null_values(db):
    """Time series should not have NULL values."""
    null_count = db.execute(
        text("SELECT COUNT(*) FROM time_series WHERE value IS NULL")
    ).scalar()
    assert null_count == 0, f"Found {null_count} NULL values in time_series"


def test_timeseries_no_negative_arrivals(db):
    """Absolute tourist arrivals should never be negative."""
    neg = db.execute(
        text("""
            SELECT COUNT(*) FROM time_series
            WHERE indicator='turistas' AND measure='ABSOLUTE' AND value < 0
        """)
    ).scalar()
    assert neg == 0, f"Found {neg} negative absolute arrivals"


def test_timeseries_period_format(db):
    """Periods should be valid date formats (YYYY, YYYY-MM, YYYY-QN)."""
    invalid = db.execute(
        text("""
            SELECT COUNT(*) FROM time_series
            WHERE period NOT GLOB '[0-9][0-9][0-9][0-9]*'
        """)
    ).scalar()
    assert invalid == 0, f"Found {invalid} records with invalid period format"


def test_timeseries_unique_constraint(db):
    """No duplicate (source, indicator, geo_code, period, measure) combos."""
    dupes = db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT source, indicator, geo_code, period, measure, COUNT(*) as cnt
                FROM time_series
                GROUP BY source, indicator, geo_code, period, measure
                HAVING cnt > 1
            )
        """)
    ).scalar()
    assert dupes == 0, f"Found {dupes} duplicate time_series records"


def test_microdata_age_range(db):
    """Tourist ages should be within reasonable bounds."""
    invalid = db.execute(
        text("""
            SELECT COUNT(*) FROM microdata
            WHERE edad IS NOT NULL AND (edad < 0 OR edad > 120)
        """)
    ).scalar()
    assert invalid == 0, f"Found {invalid} records with invalid age"


def test_microdata_nights_non_negative(db):
    """Nights stayed should not be negative."""
    neg = db.execute(
        text("SELECT COUNT(*) FROM microdata WHERE noches < 0")
    ).scalar()
    assert neg == 0, f"Found {neg} records with negative nights"


def test_microdata_spending_non_negative(db):
    """Spending should not be negative."""
    neg = db.execute(
        text("SELECT COUNT(*) FROM microdata WHERE gasto_euros < 0")
    ).scalar()
    assert neg == 0, f"Found {neg} records with negative spending"


def test_microdata_raw_json_is_valid(db):
    """All raw_json fields should be valid JSON."""
    rows = db.execute(
        text("SELECT raw_json FROM microdata WHERE raw_json IS NOT NULL LIMIT 100")
    ).fetchall()
    for r in rows:
        data = json.loads(r[0])
        assert isinstance(data, dict), "raw_json should be a dict"


def test_microdata_no_placeholder_in_key_fields(db):
    """Key fields should not contain placeholder codes like _Z, _U, _N."""
    for col in ["isla", "sexo"]:
        placeholders = db.execute(
            text(f"SELECT COUNT(*) FROM microdata WHERE {col} IN ('_Z', '_U', '_N')")
        ).scalar()
        assert placeholders == 0, (
            f"Found {placeholders} placeholder values in {col}"
        )


def test_predictions_have_valid_ci(db):
    """All predictions should have valid confidence intervals."""
    invalid = db.execute(
        text("""
            SELECT COUNT(*) FROM predictions
            WHERE ci_lower_95 > ci_lower_80
               OR ci_lower_80 > value_predicted
               OR value_predicted > ci_upper_80
               OR ci_upper_80 > ci_upper_95
        """)
    ).scalar()
    assert invalid == 0, f"Found {invalid} predictions with invalid CI ordering"


def test_profiles_cluster_ids_sequential(db):
    """Profile cluster IDs should be 0-3."""
    ids = db.execute(
        text("SELECT cluster_id FROM profiles ORDER BY cluster_id")
    ).fetchall()
    cluster_ids = [r[0] for r in ids]
    assert cluster_ids == [0, 1, 2, 3], f"Expected [0,1,2,3], got {cluster_ids}"
