"""Tests for the GET /api/profiles/nationality-trends endpoint."""


def test_nationality_trends_returns_top_nationalities(client):
    """Default request returns trend data for top 5 nationalities."""
    resp = client.get("/api/profiles/nationality-trends")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    # Each entry must have nationality and data list
    for entry in data:
        assert "nationality" in entry
        assert "data" in entry
        assert isinstance(entry["data"], list)
        assert len(entry["data"]) > 0


def test_nationality_trends_response_structure(client):
    """Each data point has the expected fields."""
    resp = client.get("/api/profiles/nationality-trends")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    point = data[0]["data"][0]
    assert "quarter" in point
    assert "count" in point
    assert "avg_spend" in point
    assert "avg_nights" in point
    assert isinstance(point["count"], int)
    assert point["count"] > 0


def test_nationality_trends_filter_by_nationality(client):
    """Filtering by nationality code returns only that nationality."""
    resp = client.get("/api/profiles/nationality-trends?nationality=826")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["nationality"] == "United Kingdom"
    # Should have data for each quarter in the test data
    assert len(data[0]["data"]) == 4  # 2024Q1-Q4


def test_nationality_trends_filter_unknown_nationality(client):
    """Filtering by unknown nationality returns empty list."""
    resp = client.get("/api/profiles/nationality-trends?nationality=999")
    assert resp.status_code == 200
    data = resp.json()
    assert data == []


def test_nationality_trends_custom_limit(client):
    """The limit parameter controls how many nationalities are returned."""
    resp = client.get("/api/profiles/nationality-trends?limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_nationality_trends_quarters_ordered(client):
    """Quarters should be returned in ascending order."""
    resp = client.get("/api/profiles/nationality-trends?nationality=826")
    assert resp.status_code == 200
    data = resp.json()
    quarters = [p["quarter"] for p in data[0]["data"]]
    assert quarters == sorted(quarters)


def test_nationality_trends_labels_resolved(client):
    """Nationality codes should be resolved to human-readable labels."""
    resp = client.get("/api/profiles/nationality-trends")
    assert resp.status_code == 200
    data = resp.json()
    names = [entry["nationality"] for entry in data]
    # All test nationalities have labels defined in NATIONALITY_LABELS
    for name in names:
        assert not name.isdigit(), f"Expected label, got raw code: {name}"


def test_nationality_trends_avg_values_reasonable(client):
    """Average spend and nights should be positive numbers when present."""
    resp = client.get("/api/profiles/nationality-trends?nationality=276")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    for point in data[0]["data"]:
        if point["avg_spend"] is not None:
            assert point["avg_spend"] > 0
        if point["avg_nights"] is not None:
            assert point["avg_nights"] > 0
