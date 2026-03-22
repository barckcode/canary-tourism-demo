"""Tests for timeseries endpoint pagination (Issue #246)."""

import math


def test_pagination_defaults(client):
    """Without page/page_size params, defaults to page=1, page_size=100."""
    r = client.get("/api/timeseries?indicator=turistas&geo=ES709")
    assert r.status_code == 200
    data = r.json()

    assert "data" in data
    assert "pagination" in data

    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 100
    assert pagination["total"] > 0
    assert pagination["total_pages"] == math.ceil(pagination["total"] / 100)
    # Default page_size=100 should cap results at 100
    assert len(data["data"]) <= 100


def test_pagination_custom_page_and_size(client):
    """Custom page and page_size should return the correct slice."""
    r1 = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=1&page_size=10"
    )
    assert r1.status_code == 200
    data1 = r1.json()
    assert len(data1["data"]) == 10
    assert data1["pagination"]["page"] == 1
    assert data1["pagination"]["page_size"] == 10

    r2 = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=2&page_size=10"
    )
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2["data"]) == 10
    assert data2["pagination"]["page"] == 2

    # Pages should not overlap
    periods_page1 = {d["period"] for d in data1["data"]}
    periods_page2 = {d["period"] for d in data2["data"]}
    assert periods_page1.isdisjoint(periods_page2), "Pages should not overlap"


def test_pagination_metadata_correctness(client):
    """Pagination metadata (total, total_pages) should be accurate."""
    # Get total count first
    r_full = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=1&page_size=500"
    )
    assert r_full.status_code == 200
    total = r_full.json()["pagination"]["total"]

    # Now request with page_size=10 and check total_pages
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=1&page_size=10"
    )
    assert r.status_code == 200
    pagination = r.json()["pagination"]
    assert pagination["total"] == total
    assert pagination["total_pages"] == math.ceil(total / 10)


def test_pagination_page_out_of_range(client):
    """Requesting a page beyond total_pages should return empty data."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=9999&page_size=100"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["data"] == []
    # Pagination metadata should still report correct totals
    assert data["pagination"]["total"] > 0
    assert data["pagination"]["page"] == 9999


def test_pagination_page_size_exceeds_max(client):
    """page_size > 500 should be rejected with HTTP 422."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page_size=501"
    )
    assert r.status_code == 422


def test_pagination_page_size_zero(client):
    """page_size=0 should be rejected with HTTP 422."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page_size=0"
    )
    assert r.status_code == 422


def test_pagination_page_zero(client):
    """page=0 should be rejected with HTTP 422."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=0"
    )
    assert r.status_code == 422


def test_pagination_negative_page(client):
    """Negative page should be rejected with HTTP 422."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709&page=-1"
    )
    assert r.status_code == 422


def test_pagination_with_date_filter(client):
    """Pagination should work correctly combined with date range filters."""
    r = client.get(
        "/api/timeseries?indicator=turistas&geo=ES709"
        "&from=2023-01&to=2023-12&page=1&page_size=5"
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) == 5
    assert data["pagination"]["total"] == 12  # 12 months in 2023
    assert data["pagination"]["total_pages"] == math.ceil(12 / 5)

    # Verify all returned periods are within the requested range
    for point in data["data"]:
        assert "2023-01" <= point["period"] <= "2023-12"
