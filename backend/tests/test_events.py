"""Tests for tourism event calendar endpoints."""

from app.db.events_seed import EVENTS, seed_events
from app.db.models import TourismEvent


# ---------------------------------------------------------------------------
# Seed function tests
# ---------------------------------------------------------------------------


def test_seed_events_populates_table(db):
    """seed_events should insert pre-defined events into an empty table."""
    # Clear any existing events first
    db.query(TourismEvent).delete()
    db.commit()

    count = seed_events(db)
    assert count == len(EVENTS)

    rows = db.query(TourismEvent).all()
    assert len(rows) == len(EVENTS)


def test_seed_events_idempotent(db):
    """seed_events should not duplicate rows when called a second time."""
    # Ensure table has data from prior test or seed it
    existing = db.query(TourismEvent).count()
    if existing == 0:
        seed_events(db)

    count = seed_events(db)
    assert count == 0, "seed_events should skip when table is already populated"


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------


def _ensure_seeded(db):
    """Helper to ensure events are seeded in the test database."""
    if db.query(TourismEvent).count() == 0:
        seed_events(db)


def test_list_events_returns_all(client, db):
    """GET /api/events should return all seeded events."""
    _ensure_seeded(db)
    r = client.get("/api/events")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert len(data["events"]) >= 12


def test_list_events_filter_by_category(client, db):
    """GET /api/events?category=connectivity should filter correctly."""
    _ensure_seeded(db)
    r = client.get("/api/events?category=connectivity")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 1
    for ev in events:
        assert ev["category"] == "connectivity"


def test_list_events_filter_by_date_range(client, db):
    """GET /api/events with from_date and to_date should filter correctly."""
    _ensure_seeded(db)
    r = client.get("/api/events?from_date=2026-03-01&to_date=2026-03-31")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 1
    for ev in events:
        # Event should overlap with March 2026
        assert ev["start_date"] <= "2026-03-31"


def test_list_events_sorted_by_start_date(client, db):
    """Events should be returned sorted by start_date ascending."""
    _ensure_seeded(db)
    r = client.get("/api/events")
    events = r.json()["events"]
    dates = [ev["start_date"] for ev in events]
    assert dates == sorted(dates)


def test_list_events_event_fields(client, db):
    """Each event should have all expected fields."""
    _ensure_seeded(db)
    r = client.get("/api/events")
    events = r.json()["events"]
    first = events[0]
    for field in ["id", "name", "category", "start_date", "source"]:
        assert field in first, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/events/categories
# ---------------------------------------------------------------------------


def test_list_categories(client, db):
    """GET /api/events/categories should return distinct categories."""
    _ensure_seeded(db)
    r = client.get("/api/events/categories")
    assert r.status_code == 200
    data = r.json()
    assert "categories" in data
    categories = data["categories"]
    assert "cultural" in categories
    assert "connectivity" in categories
    assert "regulation" in categories
    assert "external" in categories


# ---------------------------------------------------------------------------
# POST /api/events
# ---------------------------------------------------------------------------


def test_create_event(client):
    """POST /api/events should create a user event."""
    r = client.post(
        "/api/events",
        json={
            "name": "Test Music Festival",
            "description": "A test festival",
            "category": "cultural",
            "start_date": "2026-07-15",
            "end_date": "2026-07-17",
            "impact_estimate": "+3% arrivals",
            "location": "Adeje",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Test Music Festival"
    assert data["source"] == "user"
    assert data["id"] is not None


def test_create_event_minimal(client):
    """POST /api/events with only required fields should work."""
    r = client.post(
        "/api/events",
        json={
            "name": "Minimal Event",
            "category": "external",
            "start_date": "2026-08-01",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Minimal Event"
    assert data["source"] == "user"
    assert data["end_date"] is None


def test_create_event_invalid_date_format(client):
    """POST /api/events with invalid date format should return 422."""
    r = client.post(
        "/api/events",
        json={
            "name": "Bad Date Event",
            "category": "cultural",
            "start_date": "2026/07/15",
        },
    )
    assert r.status_code == 422


def test_create_event_missing_name(client):
    """POST /api/events without name should return 422."""
    r = client.post(
        "/api/events",
        json={
            "category": "cultural",
            "start_date": "2026-07-15",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/events/{event_id}
# ---------------------------------------------------------------------------


def test_delete_user_event(client):
    """DELETE /api/events/{id} should remove a user-created event."""
    # First create one
    r = client.post(
        "/api/events",
        json={
            "name": "Deletable Event",
            "category": "cultural",
            "start_date": "2026-09-01",
        },
    )
    assert r.status_code == 201
    event_id = r.json()["id"]

    # Now delete it
    r = client.delete(f"/api/events/{event_id}")
    assert r.status_code == 204

    # Verify it is gone
    r = client.get("/api/events")
    ids = [ev["id"] for ev in r.json()["events"]]
    assert event_id not in ids


def test_delete_system_event_forbidden(client, db):
    """DELETE /api/events/{id} should reject deletion of system events."""
    _ensure_seeded(db)
    # Get a system event
    r = client.get("/api/events")
    system_events = [ev for ev in r.json()["events"] if ev["source"] == "system"]
    assert len(system_events) > 0

    event_id = system_events[0]["id"]
    r = client.delete(f"/api/events/{event_id}")
    assert r.status_code == 403
    assert "user-created" in r.json()["detail"]


def test_delete_nonexistent_event(client):
    """DELETE /api/events/{id} for non-existent ID should return 404."""
    r = client.delete("/api/events/999999")
    assert r.status_code == 404
