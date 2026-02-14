"""
Integration tests for health check endpoints.
"""


def test_health_check_returns_healthy(client):
    """GET /api/health returns healthy status."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "img2stl-api"


def test_detailed_health_returns_system_info(client):
    """GET /api/health/detailed returns service info (system info removed for security)."""
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    # System info removed per QA-131 to prevent info leakage
    assert "python_version" not in data
    assert "platform" not in data
