import pytest
"""
Integration tests for the /api/v2 download endpoints.
"""
import json
import zipfile
from io import BytesIO

from api.models import FilamentColorConfig
from api.routes.download_v2 import get_colors_from_request


def test_get_filament_presets(client):
    """GET /api/v2/filament-presets returns preset list."""
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert [p["name"] for p in data["presets"]] == ["bambu_cmywk_phase6", "bambu_cmyw_phase6", "clear_cmyg", "clear_cmyw"]
    assert [p["display_name"] for p in data["presets"]] == ["Bambu CMYWK", "Bambu CMYW", "Clear CMYG", "Clear CMYW"]


def test_get_filament_presets_exposes_calibrated_material_params(client):
    """GET /api/v2/filament-presets includes calibrated blend parameters."""
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    data = response.json()

    calibrated = next(
        preset for preset in data["presets"]
        if preset["name"] == "bambu_cmyw_phase6"
    )
    cyan = next(color for color in calibrated["colors"] if color["name"] == "Cyan")

    assert cyan["transmission_distance"] == pytest.approx(2.0)
    assert cyan["k"] == 3.4996


def test_get_filament_presets_exposes_phase6_cmyw_material_params(client):
    """GET /api/v2/filament-presets includes the CMYW Phase 6 variant."""
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    data = response.json()

    phase6_cmyw = next(
        preset for preset in data["presets"]
        if preset["name"] == "bambu_cmyw_phase6"
    )
    assert len(phase6_cmyw["colors"]) == 4
    assert not any(color["name"] == "Key" for color in phase6_cmyw["colors"])


def test_get_colors_from_request_preserves_calibrated_custom_params():
    """Custom filament colors should keep calibrated blend parameters."""
    colors = get_colors_from_request(
        None,
        [
            FilamentColorConfig(
                name="Cyan", hex="#3D79C6", transmission_distance=0.49, k=1.2,
            ),
            FilamentColorConfig(
                name="Magenta", hex="#B3356E", transmission_distance=0.52, k=0.35,
            ),
            FilamentColorConfig(
                name="Yellow", hex="#FFE665", transmission_distance=0.58, k=8.4,
            ),
            FilamentColorConfig(
                name="White", hex="#FFFFFF", transmission_distance=0.61, k=6.5,
            ),
        ],
    )

    assert colors["C"].k == 1.2
    assert colors["C"].td == 0.49


def test_v2_stl_with_default_colors(client, sample_color_blocks_with_hex):
    """V2 STL with no preset or custom colors uses default Phase 6 CMYW."""
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


def test_get_colors_from_request_defaults_to_phase6_cmywk():
    """Default color resolution should use the Phase 6 CMYWK preset."""
    colors = get_colors_from_request(None, None)
    assert len(colors) == 5
    assert "K" in colors.get_labels()
    assert colors["K"].k == 23.1863
    assert colors["C"].k == 3.4996
    assert colors["W"].k == 6.3168


def test_v2_stl_with_bambu_preset(client, sample_color_blocks_with_hex):
    """V2 STL with bambu_cmyw_phase6 preset works."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            "colorBlocks": sample_color_blocks_with_hex,
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentPreset": "bambu_cmyw_phase6",
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
            "filamentPreset": "bambu_cmyw_phase6",
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
            "filamentPreset": "bambu_cmyw_phase6",
        },
    )
    assert response.status_code == 200
    buf = BytesIO(response.content)
    assert zipfile.is_zipfile(buf)


def test_print_settings_with_preset(client):
    """Print settings with preset returns valid JSON."""
    response = client.post(
        "/api/v2/print-settings",
        json={
            "layerHeight": 0.08,
            "pixelSize": 0.1,
            "layerCount": 4,
            "imageDimensions": {"width": 100, "height": 80},
            "filamentPreset": "bambu_cmyw_phase6",
        },
    )
    assert response.status_code == 200
    assert "print_settings.json" in response.headers.get("content-disposition", "")
    data = json.loads(response.content)
    assert data["version"] == "1.0"
    assert data["filament"]["preset"] == "bambu_cmyw_phase6"
    assert data["filament"]["extruder_count"] == 4
    assert data["object_dimensions"]["width_mm"] == 10.0
    assert data["object_dimensions"]["height_mm"] == 8.0
    # The full surviving schema (hex + td + k) survives serialization.
    cyan = next(e for e in data["filament"]["extruders"] if e["name"] == "Cyan")
    assert cyan["k"] == 3.4996
    assert cyan["transmission_distance"] == pytest.approx(2.0)


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


def test_print_settings_default_colors(client):
    """Print settings with no preset or custom uses default Phase 6 CMYW."""
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
    assert data["filament"]["extruder_count"] == 5
    assert data["filament"]["preset"] == "bambu_cmywk_phase6"


def test_palette_and_preset_materials_match(client):
    presets = client.get("/api/v2/filament-presets").json()["presets"]
    for preset in presets:
        palette = client.get(f"/api/palettes/{preset['name']}")
        assert palette.status_code == 200
        assert palette.json()["colors"] == preset["colors"]
