"""Tests for data seeding — verify expected record counts and data integrity."""

from sqlalchemy import text


def test_timeseries_has_records(db):
    """Time series table should have data from multiple sources."""
    count = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()
    assert count > 10000, f"Expected >10K time_series records, got {count}"


def test_timeseries_has_istac_source(db):
    """ISTAC indicators should be loaded."""
    count = db.execute(
        text("SELECT COUNT(*) FROM time_series WHERE source='istac'")
    ).scalar()
    assert count > 5000, f"Expected >5K ISTAC records, got {count}"


def test_timeseries_has_ine_source(db):
    """INE indicators should be loaded."""
    count = db.execute(
        text("SELECT COUNT(*) FROM time_series WHERE source='ine'")
    ).scalar()
    assert count > 5000, f"Expected >5K INE records, got {count}"


def test_timeseries_turistas_indicator(db):
    """Core 'turistas' indicator should exist with monthly data."""
    rows = db.execute(
        text("""
            SELECT COUNT(*) FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
              AND period LIKE '____-__'
        """)
    ).scalar()
    assert rows >= 180, f"Expected >=180 monthly arrivals records, got {rows}"


def test_timeseries_latest_period(db):
    """Latest arrivals data should reach 2026."""
    latest = db.execute(
        text("""
            SELECT MAX(period) FROM time_series
            WHERE indicator='turistas' AND geo_code='ES709' AND measure='ABSOLUTE'
        """)
    ).scalar()
    assert latest >= "2026", f"Expected latest period >= 2026, got {latest}"


def test_microdata_has_records(db):
    """Microdata table should have Tenerife tourist records."""
    count = db.execute(text("SELECT COUNT(*) FROM microdata")).scalar()
    assert count > 10000, f"Expected >10K microdata records, got {count}"


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


def test_seed_is_idempotent(db):
    """Running seed again should not duplicate records (UPSERT)."""
    count_before = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()

    from app.db.seed import seed_istac_timeseries
    from app.config import settings

    seed_istac_timeseries(db, settings.raw_data_dir)

    count_after = db.execute(text("SELECT COUNT(*) FROM time_series")).scalar()
    assert count_after == count_before, (
        f"Seed not idempotent: {count_before} -> {count_after}"
    )
