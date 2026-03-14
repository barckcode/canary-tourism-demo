"""Tests for data seeding — verify expected record counts and data integrity."""

from sqlalchemy import text


def test_timeseries_has_records(db):
    """Time series table should have data from multiple sources."""
    count = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()
    assert count > 0, f"Expected time_series records, got {count}"


def test_timeseries_has_istac_source(db):
    """ISTAC indicators should be loaded."""
    count = db.execute(
        text("SELECT COUNT(*) FROM time_series WHERE source='istac'")
    ).scalar()
    assert count > 0, f"Expected ISTAC records, got {count}"


def test_timeseries_turistas_indicator(db):
    """Core 'turistas' indicator should exist with monthly data."""
    rows = db.execute(
        text("""
            SELECT COUNT(*) FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
              AND period LIKE '____-__'
        """)
    ).scalar()
    assert rows >= 12, f"Expected >=12 monthly arrivals records, got {rows}"


def test_timeseries_latest_period(db):
    """Latest arrivals data should reach at least 2025."""
    latest = db.execute(
        text("""
            SELECT MAX(period) FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
        """)
    ).scalar()
    assert latest >= "2025", f"Expected latest period >= 2025, got {latest}"


def test_microdata_has_records(db):
    """Microdata table should have Tenerife tourist records."""
    count = db.execute(text("SELECT COUNT(*) FROM microdata")).scalar()
    assert count > 0, f"Expected microdata records, got {count}"


def test_microdata_has_four_quarters(db):
    """Microdata should span 4 quarters."""
    quarters = db.execute(
        text("SELECT DISTINCT quarter FROM microdata ORDER BY quarter")
    ).fetchall()
    quarter_list = [q[0] for q in quarters]
    assert len(quarter_list) == 4, f"Expected 4 quarters, got {quarter_list}"


def test_microdata_tenerife_only(db):
    """All microdata records should be for Tenerife (ES709)."""
    non_tf = db.execute(
        text("SELECT COUNT(*) FROM microdata WHERE isla != 'ES709'")
    ).scalar()
    assert non_tf == 0, f"Expected 0 non-Tenerife records, got {non_tf}"


def test_microdata_has_spending_data(db):
    """Microdata should have valid spending values."""
    avg_spend = db.execute(
        text("SELECT AVG(gasto_euros) FROM microdata WHERE gasto_euros > 0")
    ).scalar()
    assert avg_spend is not None
    assert 100 < avg_spend < 5000, f"Avg spend {avg_spend} outside expected range"


def test_microdata_has_raw_json(db):
    """Every microdata record should have raw_json populated."""
    missing = db.execute(
        text("SELECT COUNT(*) FROM microdata WHERE raw_json IS NULL")
    ).scalar()
    assert missing == 0, f"Expected 0 records without raw_json, got {missing}"
