"""
Integration tests for security hardening.
"""
import io

from PIL import Image


def test_reject_non_image_extension(client):
    """Uploading a .txt file returns 400."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.txt", b"hello world", "text/plain")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_reject_fake_magic_bytes(client):
    """File with .png extension but non-image content returns 400."""
    response = client.post(
        "/api/process-image",
        files={"image": ("fake.png", b"not a real png file", "image/png")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"]


def test_reject_empty_file(client):
    """Empty file upload returns 400."""
    response = client.post(
        "/api/process-image",
        files={"image": ("empty.png", b"", "image/png")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 400
    assert "Empty file" in response.json()["detail"]


def test_reject_oversized_file(client):
    """File exceeding max_upload_size returns 413."""
    # Create a file larger than 10MB
    oversized = b"\x89PNG" + b"\x00" * (11 * 1024 * 1024)
    response = client.post(
        "/api/process-image",
        files={"image": ("large.png", oversized, "image/png")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_error_responses_contain_no_stack_traces(client):
    """500 errors do not leak internal details."""
    # Send a valid-looking PNG that will fail during actual processing
    # but passes validation (has PNG magic bytes)
    truncated_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = client.post(
        "/api/process-image",
        files={"image": ("broken.png", truncated_png, "image/png")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    # Should be 500 (internal error during processing)
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert detail == "An internal error occurred"
    assert "Traceback" not in detail
    assert "File" not in detail


def test_cors_headers_present(client):
    """CORS headers are set on responses."""
    response = client.options(
        "/api/process-image",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    # CORS preflight should succeed for allowed origin
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


def test_cors_disallowed_methods(client):
    """CORS rejects methods not in the allowed list."""
    response = client.options(
        "/api/process-image",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    # DELETE should not be in allow-methods
    allow_methods = response.headers.get("access-control-allow-methods", "")
    assert "DELETE" not in allow_methods
