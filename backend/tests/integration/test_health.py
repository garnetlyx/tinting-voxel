"""
Integration tests for health check endpoints.
"""


def test_root_returns_200(client):
    """GET / returns 200 with status ok."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_health_check_returns_healthy(client):
    """GET /health returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "img2stl-api"


def test_detailed_health_returns_system_info(client):
    """GET /health/detailed returns service info (system info removed for security)."""
    response = client.get("/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    # System info removed per QA-131 to prevent info leakage
    assert "python_version" not in data
    assert "platform" not in data
