"""
Integration tests for the /api/process-image endpoint.
"""
import io


def test_pixel_mode_success(client, tiny_png_bytes):
    """POST /api/process-image in pixel mode returns colorBlocks and image."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "4", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "colorBlocks" in data
    assert "processedImage" in data
    assert "segmentationImage" in data
    assert "mappedBlockColors" in data
    assert "mappedBlendPalette" in data
    assert "imageDimensions" in data
    assert len(data["colorBlocks"]) > 0


def test_svg_mode_success(client, tiny_png_bytes):
    """POST /api/process-image in svg mode returns vectorResults."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "svg", "epsilon": "1.0", "minArea": "1", "numColors": "4", "pixelSize": "0.08"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "vectorResults" in data
    assert "processedImage" in data
    assert "imageDimensions" in data


def test_max_colors_respected(client, tiny_png_bytes):
    """maxColors parameter limits the number of extracted colors."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "2", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["colorBlocks"]) <= 2


def test_invalid_mode_returns_422(client, tiny_png_bytes):
    """Invalid mode value returns 422."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "invalid_mode", "pixelSize": "0.08"},
    )
    # Invalid mode returns 400 (explicitly caught ValueError)
    assert response.status_code == 400


def test_no_file_returns_422(client):
    """Missing image file returns 422."""
    response = client.post(
        "/api/process-image",
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 422


def test_corrupt_file_returns_400(client):
    """Corrupt file with valid extension but bad content returns 400."""
    corrupt_bytes = b"this is not an image file at all"
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", corrupt_bytes, "image/png")},
        data={"mode": "pixel", "pixelSize": "0.08"},
    )
    assert response.status_code == 400


def test_color_blocks_have_required_fields(client, tiny_png_bytes):
    """Each color block has r, g, b, count, pixels, hex fields."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "4", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert response.status_code == 200
    for block in response.json()["colorBlocks"]:
        assert "r" in block
        assert "g" in block
        assert "b" in block
        assert "count" in block
        assert "pixels" in block
        assert "hex" in block


def test_dimensions_match_input(client, tiny_png_bytes):
    """Returned imageDimensions match the uploaded image size."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "4", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert response.status_code == 200
    dims = response.json()["imageDimensions"]
    assert dims["width"] == 4
    assert dims["height"] == 4


def test_simulate_preview_success(client, tiny_png_bytes):
    """POST /api/simulate-preview returns image-specific mapped palette data."""
    process_response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "4", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert process_response.status_code == 200
    processed = process_response.json()

    response = client.post(
        "/api/simulate-preview",
        json={
            "colorBlocks": processed["colorBlocks"],
            "imageDimensions": processed["imageDimensions"],
            "layerHeight": 0.08,
            "layerCount": 4,
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "processedImage" in data
    assert "mappedBlockColors" in data
    assert "mappedBlendPalette" in data
    assert len(data["mappedBlendPalette"]) > 0
