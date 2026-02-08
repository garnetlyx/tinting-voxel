"""
Integration tests for the /api/v2 download endpoints.
"""
import json
import zipfile
from io import BytesIO


def test_get_filament_presets(client):
    """GET /api/v2/filament-presets returns preset list."""
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert len(data["presets"]) == 2
    names = [p["name"] for p in data["presets"]]
    assert "bambu_cmyk" in names
    assert "clear_cmyk" in names


def test_v2_stl_with_default_colors(client, sample_color_blocks_with_hex):
    """V2 STL with no preset or custom colors uses default CMYK."""
    response = client.post(
        "/api/v2/download-stl",
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
    assert len(zf.namelist()) > 0


def test_v2_stl_with_bambu_preset(client, sample_color_blocks_with_hex):
    """V2 STL with bambu_cmyk preset works."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_v2_stl_with_custom_colors(client, sample_color_blocks_with_hex):
    """V2 STL with 4 custom colors works."""
    custom_colors = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#FF00FF", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
    ]
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentColors": custom_colors,
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_v2_stl_too_few_colors_returns_422(client, sample_color_blocks_with_hex):
    """V2 STL with only 3 custom colors returns 422."""
    too_few = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#FF00FF", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
    ]
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentColors": too_few,
        },
    )
    assert response.status_code == 422


def test_v2_stl_duplicate_labels_returns_422(client, sample_color_blocks_with_hex):
    """V2 STL with duplicate first-letter labels returns 422."""
    duplicates = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Crimson", "hex": "#DC143C", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
    ]
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentColors": duplicates,
        },
    )
    assert response.status_code == 422


def test_v2_stl_with_base_plate(client, sample_color_blocks_with_hex):
    """V2 STL with base plate thickness generates extra base STL file."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "basePlateThickness": 0.5,
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    filenames = zf.namelist()
    assert len(filenames) > 0
    base_files = [f for f in filenames if '_base.stl' in f]
    assert len(base_files) == 1, f"Expected 1 base plate file, got {base_files}"


def test_v2_stl_without_base_plate(client, sample_color_blocks_with_hex):
    """V2 STL with no base plate thickness has no base file."""
    response = client.post(
        "/api/v2/download-stl",
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
    filenames = zf.namelist()
    base_files = [f for f in filenames if '_base.stl' in f]
    assert len(base_files) == 0, f"Expected no base plate file, got {base_files}"


def test_v2_stl_base_plate_zero_thickness(client, sample_color_blocks_with_hex):
    """V2 STL with basePlateThickness=0 has no base file."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "basePlateThickness": 0,
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    filenames = zf.namelist()
    base_files = [f for f in filenames if '_base.stl' in f]
    assert len(base_files) == 0, f"Expected no base plate file with thickness=0"


def test_v2_stl_base_plate_invalid_thickness(client, sample_color_blocks_with_hex):
    """V2 STL with basePlateThickness > 10 returns 422."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "basePlateThickness": 15.0,
        },
    )
    assert response.status_code == 422


def test_v2_stl_double_sided(client, sample_color_blocks_with_hex):
    """V2 STL with doubleSided=True generates larger ZIP (more mesh data)."""
    # Single-sided
    response_single = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    assert response_single.status_code == 200

    # Double-sided
    response_double = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "doubleSided": True,
        },
    )
    assert response_double.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response_double.content))
    assert len(zf.namelist()) > 0
    # Double-sided output should be larger than single-sided
    assert len(response_double.content) > len(response_single.content)


def test_v2_stl_double_sided_with_base_plate(client, sample_color_blocks_with_hex):
    """V2 STL with doubleSided=True and base plate works together."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "doubleSided": True,
            "basePlateThickness": 0.5,
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    filenames = zf.namelist()
    assert len(filenames) > 0
    base_files = [f for f in filenames if '_base.stl' in f]
    assert len(base_files) == 1


def test_v2_stl_double_sided_false_same_as_default(client, sample_color_blocks_with_hex):
    """V2 STL with doubleSided=False produces same result as not specifying it."""
    payload = {
        "colorBlocks": sample_color_blocks_with_hex,
        "layerHeight": 0.08,
        "pixelSize": 0.08,
        "layerCount": 4,
        "imageDimensions": {"width": 4, "height": 4},
    }
    response_default = client.post("/api/v2/download-stl", json=payload)
    payload["doubleSided"] = False
    response_false = client.post("/api/v2/download-stl", json=payload)

    assert response_default.status_code == 200
    assert response_false.status_code == 200
    assert len(response_default.content) == len(response_false.content)


def test_v2_svg_stl_with_base_plate(client):
    """V2 SVG STL with base plate generates extra base STL file."""
    vector_results = [
        {
            "color": [255, 0, 0],
            "polygons": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
            "pixel_count": 100,
            "polygon_points": 4,
        }
    ]
    response = client.post(
        "/api/v2/download-svg-stl",
        json={
            "vectorResults": vector_results,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 10, "height": 10},
            "filamentPreset": "bambu_cmyk",
            "basePlateThickness": 0.5,
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    filenames = zf.namelist()
    base_files = [f for f in filenames if '_base.stl' in f]
    assert len(base_files) == 1, f"Expected 1 base plate file, got {base_files}"


def test_v2_svg_stl_success(client):
    """V2 SVG STL endpoint works."""
    vector_results = [
        {
            "color": [255, 0, 0],
            "polygons": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
            "pixel_count": 100,
            "polygon_points": 4,
        }
    ]
    response = client.post(
        "/api/v2/download-svg-stl",
        json={
            "vectorResults": vector_results,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 10, "height": 10},
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


# -- 3MF endpoint tests --

def test_v2_3mf_with_default_colors(client, sample_color_blocks_with_hex):
    """V2 3MF with default colors returns valid 3MF file."""
    response = client.post(
        "/api/v2/download-3mf",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
        },
    )
    assert response.status_code == 200
    assert "3mf" in response.headers.get("content-disposition", "")
    buf = BytesIO(response.content)
    assert zipfile.is_zipfile(buf)


def test_v2_3mf_with_preset(client, sample_color_blocks_with_hex):
    """V2 3MF with preset returns valid 3MF."""
    response = client.post(
        "/api/v2/download-3mf",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    buf = BytesIO(response.content)
    assert zipfile.is_zipfile(buf)


def test_v2_3mf_with_base_plate(client, sample_color_blocks_with_hex):
    """V2 3MF with base plate succeeds."""
    response = client.post(
        "/api/v2/download-3mf",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "basePlateThickness": 0.5,
        },
    )
    assert response.status_code == 200


# -- Print Settings endpoint tests --

def test_print_settings_with_preset(client):
    """Print settings with preset returns valid JSON."""
    response = client.post(
        "/api/v2/print-settings",
        json={
            "layerHeight": 0.08,
            "pixelSize": 0.1,
            "layerCount": 4,
            "imageDimensions": {"width": 100, "height": 80},
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    assert "print_settings.json" in response.headers.get("content-disposition", "")
    data = json.loads(response.content)
    assert data["version"] == "1.0"
    assert data["filament"]["preset"] == "bambu_cmyk"
    assert data["filament"]["extruder_count"] == 4
    assert data["object_dimensions"]["width_mm"] == 10.0
    assert data["object_dimensions"]["height_mm"] == 8.0


def test_print_settings_with_custom_colors(client):
    """Print settings with custom filament colors returns correct extruders."""
    custom_colors = [
        {"name": "Cyan", "hex": "#0086D6", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#EC008C", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#F4EE2A", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
    ]
    response = client.post(
        "/api/v2/print-settings",
        json={
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 50, "height": 50},
            "filamentColors": custom_colors,
        },
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["filament"]["preset"] is None
    assert data["filament"]["extruder_count"] == 4
    assert data["filament"]["extruders"][0]["name"] == "Cyan"


def test_print_settings_with_base_plate(client):
    """Print settings includes base plate in total height."""
    response = client.post(
        "/api/v2/print-settings",
        json={
            "layerHeight": 0.1,
            "pixelSize": 0.1,
            "layerCount": 4,
            "imageDimensions": {"width": 10, "height": 10},
            "basePlateThickness": 0.5,
            "filamentPreset": "bambu_cmyk",
        },
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["print_settings"]["base_plate_thickness"] == 0.5
    assert data["object_dimensions"]["total_height_mm"] == 0.9


def test_print_settings_default_colors(client):
    """Print settings with no preset or custom uses default CMYK."""
    response = client.post(
        "/api/v2/print-settings",
        json={
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 10, "height": 10},
        },
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["filament"]["extruder_count"] == 4
    assert data["filament"]["preset"] == "bambu_cmyk"
