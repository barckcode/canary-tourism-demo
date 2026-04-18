"""Tests for timeseries period validation and null filtering (Issue #642)."""


def test_timeseries_from_after_to_returns_400(client):
    """Requesting from > to should return HTTP 400 with descriptive message."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&from=2025-06&to=2024-01"
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "before or equal" in detail


def test_timeseries_from_equals_to_succeeds(client):
    """from == to should be accepted (single-month query)."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&from=2024-06&to=2024-06"
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(d["period"] == "2024-06" for d in data)


def test_timeseries_null_values_excluded(client, db):
    """Rows with value=None should be excluded from the response data."""
    from app.db.models import TimeSeries

    # Insert a row with a null value
    db.add(TimeSeries(
        source="test",
        indicator="test_null_indicator",
        geo_code="ES709",
        period="2024-01",
        measure="ABSOLUTE",
        value=None,
    ))
    # Insert a row with a real value
    db.add(TimeSeries(
        source="test",
        indicator="test_null_indicator",
        geo_code="ES709",
        period="2024-02",
        measure="ABSOLUTE",
        value=42.0,
    ))
    db.commit()

    r = client.get("/api/timeseries?indicator=test_null_indicator&geo=ES709")
    assert r.status_code == 200
    data = r.json()["data"]
    # Only the non-null row should appear
    assert len(data) == 1
    assert data[0]["period"] == "2024-02"
    assert data[0]["value"] == 42.0
