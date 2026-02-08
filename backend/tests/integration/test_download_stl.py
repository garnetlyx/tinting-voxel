"""
Integration tests for the /api/download-stl and /api/download-svg-stl endpoints.
"""
import struct
import zipfile
from io import BytesIO


def test_pixel_stl_success(client, sample_color_blocks_with_hex):
    """POST /api/download-stl returns a valid ZIP file."""
    response = client.post(
        "/api/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_zip_contains_stl_files(client, sample_color_blocks_with_hex):
    """ZIP archive contains .stl files with color labels in names."""
    response = client.post(
        "/api/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    stl_files = [n for n in zf.namelist() if n.endswith('.stl')]
    assert len(stl_files) > 0


def test_stl_binary_format(client, sample_color_blocks_with_hex):
    """STL files in ZIP have valid binary STL format (80-byte header + triangle count)."""
    response = client.post(
        "/api/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    zf = zipfile.ZipFile(BytesIO(response.content))
    stl_files = [n for n in zf.namelist() if n.endswith('.stl')]

    for stl_name in stl_files:
        stl_data = zf.read(stl_name)
        # Binary STL: 80 byte header + 4 byte triangle count
        assert len(stl_data) >= 84, f"{stl_name} too short for binary STL"
        triangle_count = struct.unpack('<I', stl_data[80:84])[0]
        # Each triangle = 50 bytes (normal + 3 vertices + attribute)
        expected_size = 84 + triangle_count * 50
        assert len(stl_data) == expected_size, (
            f"{stl_name}: expected {expected_size} bytes, got {len(stl_data)}"
        )


def test_svg_stl_success(client):
    """POST /api/download-svg-stl returns a valid ZIP."""
    vector_results = [
        {
            "color": [255, 0, 0],
            "polygons": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
            "pixel_count": 100,
            "polygon_points": 4,
        }
    ]
    response = client.post(
        "/api/download-svg-stl",
        json={
            "vectorResults": vector_results,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 10, "height": 10},
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_invalid_layer_count_returns_422(client, sample_color_blocks_with_hex):
    """layerCount=0 returns 422."""
    response = client.post(
        "/api/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 0,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    assert response.status_code == 422


def test_missing_fields_returns_422(client):
    """Missing required fields returns 422."""
    response = client.post(
        "/api/download-stl",
        json={"colorBlocks": []},
    )
    assert response.status_code == 422


def test_full_pipeline(client, tiny_png_bytes):
    """End-to-end: upload image -> extract colors -> generate STL."""
    # Step 1: Process image
    process_response = client.post(
        "/api/process-image",
        files={"image": ("test.png", tiny_png_bytes, "image/png")},
        data={"mode": "pixel", "maxColors": "4", "colorThreshold": "50", "pixelSize": "0.08"},
    )
    assert process_response.status_code == 200
    process_data = process_response.json()

    # Step 2: Generate STL from extracted colors
    stl_response = client.post(
        "/api/download-stl",
        json={
            "colorBlocks": process_data["colorBlocks"],
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": process_data["imageDimensions"],
        },
    )
    assert stl_response.status_code == 200

    zf = zipfile.ZipFile(BytesIO(stl_response.content))
    stl_files = [n for n in zf.namelist() if n.endswith('.stl')]
    assert len(stl_files) > 0
