"""Tests for the GET /api/events/{event_id}/impact endpoint."""

from app.db.events_seed import EVENTS, seed_events
from app.db.models import TimeSeries, TourismEvent


def _ensure_seeded(db):
    """Helper to ensure events are seeded in the test database."""
    if db.query(TourismEvent).count() == 0:
        seed_events(db)


# ---------------------------------------------------------------------------
# GET /api/events/{event_id}/impact
# ---------------------------------------------------------------------------


def test_event_impact_returns_kpis(client, db):
    """GET /api/events/{id}/impact should return KPI data for an event."""
    _ensure_seeded(db)

    # Pick an event whose dates overlap with test time_series data (2022-2025)
    # Carnaval 2025: 2025-01-17 to 2025-02-23 -> periods 2025-01, 2025-02
    event = db.query(TourismEvent).filter(
        TourismEvent.name.like("%Carnaval%2025%")
    ).first()
    assert event is not None, "Carnaval 2025 should exist in seed data"

    r = client.get(f"/api/events/{event.id}/impact")
    assert r.status_code == 200

    data = r.json()
    assert data["event_id"] == event.id
    assert data["event_name"] == event.name
    assert data["category"] == "cultural"
    assert "current_kpis" in data
    assert "previous_year_kpis" in data
    assert "yoy_changes" in data

    # Should have KPI entries for the event periods
    assert len(data["current_kpis"]) > 0
    assert len(data["previous_year_kpis"]) > 0

    # YoY changes should contain all expected indicators
    expected_indicators = [
        "turistas",
        "alojatur_ocupacion",
        "alojatur_adr",
        "alojatur_revpar",
        "alojatur_pernoctaciones",
    ]
    for ind in expected_indicators:
        assert ind in data["yoy_changes"]


def test_event_impact_yoy_values_are_numeric(client, db):
    """YoY changes should be numeric percentages when data exists."""
    _ensure_seeded(db)

    event = db.query(TourismEvent).filter(
        TourismEvent.name.like("%Carnaval%2025%")
    ).first()
    assert event is not None

    r = client.get(f"/api/events/{event.id}/impact")
    data = r.json()

    # With our test data, turistas has values for 2024 and 2025
    # so YoY change should be a float, not None
    turistas_yoy = data["yoy_changes"].get("turistas")
    assert turistas_yoy is not None, "turistas YoY should be calculable"
    assert isinstance(turistas_yoy, float)


def test_event_impact_not_found(client):
    """GET /api/events/999999/impact should return 404."""
    r = client.get("/api/events/999999/impact")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_event_impact_single_day_event(client, db):
    """Impact endpoint should work for single-day events (no end_date)."""
    _ensure_seeded(db)

    # Create a single-day user event within the test data range
    r = client.post(
        "/api/events",
        json={
            "name": "Test Single Day Event",
            "category": "cultural",
            "start_date": "2025-06-15",
        },
    )
    assert r.status_code == 201
    event_id = r.json()["id"]

    r = client.get(f"/api/events/{event_id}/impact")
    assert r.status_code == 200

    data = r.json()
    assert data["event_id"] == event_id
    # start_date and end_date should both be the same day
    assert data["start_date"] == "2025-06-15"
    assert data["end_date"] == "2025-06-15"


def test_event_impact_no_data_returns_empty(client, db):
    """Impact for an event with no matching time_series should return empty KPIs."""
    # Create an event far in the future with no matching data
    r = client.post(
        "/api/events",
        json={
            "name": "Far Future Event",
            "category": "cultural",
            "start_date": "2099-01-15",
        },
    )
    assert r.status_code == 201
    event_id = r.json()["id"]

    r = client.get(f"/api/events/{event_id}/impact")
    assert r.status_code == 200

    data = r.json()
    assert data["current_kpis"] == []
    assert data["previous_year_kpis"] == []
    # All YoY changes should be None when no data exists
    for val in data["yoy_changes"].values():
        assert val is None


def test_event_impact_response_fields(client, db):
    """Response should include all required fields from EventImpactResponse."""
    _ensure_seeded(db)

    event = db.query(TourismEvent).filter(
        TourismEvent.name.like("%Semana Santa 2025%")
    ).first()
    assert event is not None

    r = client.get(f"/api/events/{event.id}/impact")
    assert r.status_code == 200

    data = r.json()
    required_fields = [
        "event_id", "event_name", "start_date", "end_date",
        "category", "current_kpis", "previous_year_kpis", "yoy_changes",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"


def test_event_impact_kpi_structure(client, db):
    """Each KPI entry should have indicator, period, and value fields."""
    _ensure_seeded(db)

    event = db.query(TourismEvent).filter(
        TourismEvent.name.like("%Carnaval%2025%")
    ).first()
    assert event is not None

    r = client.get(f"/api/events/{event.id}/impact")
    data = r.json()

    for kpi in data["current_kpis"]:
        assert "indicator" in kpi
        assert "period" in kpi
        assert "value" in kpi
