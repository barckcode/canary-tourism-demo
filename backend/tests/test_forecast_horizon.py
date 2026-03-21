"""Tests for forecast horizon metadata in the predictions endpoint (issue #232).

The GET /api/predictions response must include:
- requested_horizon: the horizon the client asked for
- actual_horizon: how many forecast points are actually returned
- complete: True only when actual_horizon >= requested_horizon
"""


def test_horizon_metadata_fields_present(client):
    """Response must contain the three new metadata fields."""
    r = client.get("/api/predictions", params={"indicator": "turistas", "geo": "ES709"})
    assert r.status_code == 200
    data = r.json()
    assert "requested_horizon" in data
    assert "actual_horizon" in data
    assert "complete" in data


def test_horizon_complete_true(client):
    """When enough predictions exist, complete should be True."""
    # The test DB seeds 12 predictions per model, so horizon=12 should be complete
    r = client.get(
        "/api/predictions",
        params={"indicator": "turistas", "geo": "ES709", "horizon": 12},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requested_horizon"] == 12
    assert data["actual_horizon"] == 12
    assert data["complete"] is True


def test_horizon_complete_false_when_truncated(client):
    """When fewer predictions exist than requested, complete should be False."""
    # The test DB has only 12 predictions, so requesting 24 should truncate
    r = client.get(
        "/api/predictions",
        params={"indicator": "turistas", "geo": "ES709", "horizon": 24},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requested_horizon"] == 24
    assert data["actual_horizon"] == 12
    assert data["complete"] is False


def test_horizon_default_value(client):
    """When no horizon is specified, the default (12) should be used."""
    r = client.get(
        "/api/predictions",
        params={"indicator": "turistas", "geo": "ES709"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requested_horizon"] == 12


def test_horizon_smaller_than_available(client):
    """Requesting fewer periods than available should still be complete."""
    r = client.get(
        "/api/predictions",
        params={"indicator": "turistas", "geo": "ES709", "horizon": 6},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["requested_horizon"] == 6
    assert data["actual_horizon"] == 6
    assert data["complete"] is True
    assert len(data["forecast"]) == 6
