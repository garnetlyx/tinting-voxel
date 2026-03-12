"""
Integration tests for the /api/process-image endpoint.
"""
import io

from PIL import Image


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
    assert "segmentationImage" in data
    assert "mappedBlendPalette" in data
    assert "imageDimensions" in data
    assert data["processedImage"].startswith("data:image/png;base64,")
    assert data["segmentationImage"].startswith("data:image/png;base64,")


def test_svg_mode_ignores_detail_size_for_global_resizing(client, tiny_png_bytes):
    """detailSize no longer forces SVG mode to resample the full image."""
    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={
            "mode": "svg",
            "epsilon": "1.0",
            "minArea": "1",
            "numColors": "4",
            "pixelSize": "0.08",
            "detailSize": "0.4",
            "targetWidth": "100",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imageDimensions"]["width"] == 4
    assert data["imageDimensions"]["height"] == 4


def test_svg_mode_removes_tiny_island_with_detail_size(client):
    """SVG mode merges away a sub-threshold island before contour extraction."""
    pixels = Image.new("RGB", (5, 5), (255, 0, 0))
    pixels.putpixel((2, 2), (0, 0, 255))
    image_bytes = io.BytesIO()
    pixels.save(image_bytes, format="PNG")

    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", image_bytes.getvalue(), "image/png")},
        data={
            "mode": "svg",
            "epsilon": "1.0",
            "minArea": "1",
            "numColors": "2",
            "pixelSize": "0.2",
            "detailSize": "0.4",
        },
    )

    assert response.status_code == 200
    colors = {tuple(result["color"]) for result in response.json()["vectorResults"]}
    assert (0, 0, 255) not in colors


def test_svg_mode_keeps_threshold_sized_island(client):
    """SVG mode preserves an island that meets the detail threshold."""
    image = Image.new("RGB", (7, 7), (255, 0, 0))
    for x in range(2, 5):
        for y in range(2, 5):
            image.putpixel((x, y), (0, 0, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    response = client.post(
        "/api/process-image",
        files={"image": ("test.png", buffer.getvalue(), "image/png")},
        data={
            "mode": "svg",
            "epsilon": "1.0",
            "minArea": "1",
            "numColors": "2",
            "pixelSize": "0.2",
            "detailSize": "0.4",
        },
    )

    assert response.status_code == 200
    colors = {tuple(result["color"]) for result in response.json()["vectorResults"]}
    assert (0, 0, 255) in colors


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
