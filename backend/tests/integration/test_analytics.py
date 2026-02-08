"""
Integration tests for /api/analytics endpoint.
"""
from services.analytics import analytics


def test_analytics_endpoint_returns_200(client):
    """GET /api/analytics returns 200 with summary data."""
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert "startedAt" in data
    assert "totalRequests" in data
    assert "totalErrors" in data
    assert "endpoints" in data


def test_analytics_tracks_requests(client):
    """Analytics tracks requests after palette listing."""
    analytics.reset()

    # Make a request that will be tracked
    client.get("/api/palettes/")

    # Check analytics
    response = client.get("/api/analytics")
    data = response.json()

    # Should have at least the palettes request
    assert data["totalRequests"] >= 1
    assert "GET /api/palettes/" in data["endpoints"]


def test_analytics_tracks_error_requests(client):
    """Analytics tracks 404 and other error responses."""
    analytics.reset()

    # Trigger a 404
    client.get("/api/palettes/nonexistent_palette_xyz")

    response = client.get("/api/analytics")
    data = response.json()
    assert data["totalErrors"] >= 1
