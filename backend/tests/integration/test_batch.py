"""
Integration tests for /api/batch/ endpoints.
"""
import io
import zipfile

from PIL import Image


def _make_png(width=4, height=4, color=(255, 0, 0)):
    """Create a small PNG image as bytes."""
    img = Image.new('RGB', (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestBatchProcess:
    """Tests for POST /api/batch/process."""

    def test_single_image(self, client):
        """Process a single image in batch mode."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/process",
            files=[("images", ("test.png", png_bytes, "image/png"))],
            data={"maxColors": "10", "colorThreshold": "50", "pixelSize": "0.08"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalImages"] == 1
        assert data["successCount"] == 1
        assert data["errorCount"] == 0
        assert len(data["results"]) == 1
        assert data["results"][0]["status"] == "success"
        assert data["results"][0]["filename"] == "test.png"

    def test_multiple_images(self, client):
        """Process multiple images in batch mode."""
        files = [
            ("images", ("red.png", _make_png(color=(255, 0, 0)), "image/png")),
            ("images", ("green.png", _make_png(color=(0, 255, 0)), "image/png")),
            ("images", ("blue.png", _make_png(color=(0, 0, 255)), "image/png")),
        ]
        response = client.post(
            "/api/batch/process",
            files=files,
            data={"maxColors": "10"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalImages"] == 3
        assert data["successCount"] == 3

    def test_mixed_valid_invalid(self, client):
        """Mix of valid and invalid images returns partial success."""
        files = [
            ("images", ("good.png", _make_png(), "image/png")),
            ("images", ("bad.txt", b"not an image", "text/plain")),
        ]
        response = client.post(
            "/api/batch/process",
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["totalImages"] == 2
        assert data["successCount"] == 1
        assert data["errorCount"] == 1

    def test_no_images_returns_400(self, client):
        """No images provided returns 400."""
        response = client.post("/api/batch/process")
        assert response.status_code == 422  # FastAPI validation

    def test_result_contains_color_blocks(self, client):
        """Successful result contains colorBlocks and imageDimensions."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/process",
            files=[("images", ("test.png", png_bytes, "image/png"))],
        )
        data = response.json()
        result = data["results"][0]
        assert "colorBlocks" in result
        assert len(result["colorBlocks"]) > 0
        assert "imageDimensions" in result
        assert result["imageDimensions"]["width"] == 4
        assert result["imageDimensions"]["height"] == 4


class TestBatchDownloadSTL:
    """Tests for POST /api/batch/download-stl."""

    def test_single_image_stl_download(self, client):
        """Download STL ZIP for a single image."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/download-stl",
            files=[("images", ("test.png", png_bytes, "image/png"))],
            data={
                "maxColors": "10",
                "pixelSize": "0.08",
                "layerHeight": "0.08",
                "layerCount": "4",
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

        # Verify it's a valid ZIP containing the expected inner ZIP
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            assert "test.zip" in zf.namelist()

    def test_multiple_images_stl_download(self, client):
        """Download STL ZIPs for multiple images."""
        files = [
            ("images", ("alpha.png", _make_png(color=(255, 0, 0)), "image/png")),
            ("images", ("beta.png", _make_png(color=(0, 255, 0)), "image/png")),
        ]
        response = client.post(
            "/api/batch/download-stl",
            files=files,
            data={
                "maxColors": "10",
                "pixelSize": "0.08",
                "layerHeight": "0.08",
                "layerCount": "4",
            },
        )
        assert response.status_code == 200

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            names = zf.namelist()
            assert "alpha.zip" in names
            assert "beta.zip" in names

    def test_all_invalid_images_returns_422(self, client):
        """All images failing returns 422."""
        files = [
            ("images", ("bad.txt", b"not an image", "text/plain")),
        ]
        response = client.post(
            "/api/batch/download-stl",
            files=files,
        )
        assert response.status_code == 422

    def test_with_filament_preset(self, client):
        """STL download with filament preset."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/download-stl",
            files=[("images", ("test.png", png_bytes, "image/png"))],
            data={
                "maxColors": "10",
                "pixelSize": "0.08",
                "layerHeight": "0.08",
                "layerCount": "4",
                "filamentPreset": "bambu_cmyw",
            },
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
    def test_content_disposition_header(self, client):
        """Response has correct content-disposition header."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/download-stl",
            files=[("images", ("test.png", png_bytes, "image/png"))],
            data={
                "pixelSize": "0.08",
                "layerHeight": "0.08",
                "layerCount": "4",
            },
        )
        assert response.status_code == 200
        assert "batch_stl_output.zip" in response.headers.get("content-disposition", "")

    def test_allows_pixel_size_smaller_than_detail_size(self, client):
        """Batch STL download uses local detail merging instead of rejecting the request."""
        png_bytes = _make_png()
        response = client.post(
            "/api/batch/download-stl",
            files=[("images", ("test.png", png_bytes, "image/png"))],
            data={
                "pixelSize": "0.2",
                "detailSize": "0.4",
                "layerHeight": "0.08",
                "layerCount": "4",
            },
        )
        assert response.status_code == 200
