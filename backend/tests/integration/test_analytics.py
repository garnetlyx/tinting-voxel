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


def test_requests_are_keyed_by_route_template(client):
    """Parameterized and unknown paths cannot grow the key set (QA-119)."""
    analytics.reset()
    for palette_id in ("first", "second", "third"):
        client.get(f"/api/palettes/{palette_id}")
    client.get("/api/does-not-exist/1")
    client.get("/api/does-not-exist/2")

    endpoints = client.get("/api/analytics").json()["endpoints"]
    assert endpoints["GET /api/palettes/{palette_id}"]["requestCount"] == 3
    assert endpoints["GET unmatched"]["requestCount"] == 2
    assert not any("first" in key or "does-not-exist" in key for key in endpoints)


def test_v2_endpoints_are_tracked_individually(client):
    """Every registered route keeps its own key (QA-134, QA-151)."""
    analytics.reset()
    client.get("/api/v2/filament-presets")
    client.get("/api/health")

    endpoints = client.get("/api/analytics").json()["endpoints"]
    assert "GET /api/v2/filament-presets" in endpoints
    assert "GET /api/health" in endpoints


def test_summary_counts_telemetry_events(client):
    analytics.reset()
    client.get("/api/health")
    assert client.get("/api/analytics").json()["events"]["api_request"] >= 1
