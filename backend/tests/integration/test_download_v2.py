"""Integration tests for the /api/v2 download endpoints."""
import pytest
import json
import zipfile
import struct
from config.print_defaults import MAX_COLOR_LAYERS
from config.settings import settings
from services.image_processor import MAX_PROCESSING_DIMENSION

import numpy as np
import trimesh
from io import BytesIO

from api.models import FilamentColorConfig
from api.filament_payload import get_colors_from_request
from core.blend_color import Colors, colors_key
from core.blend_models import codes_to_rgb_batch
from core.color_config import ColorConfig, get_preset
from core.stack_prune import is_translucent_set
from tests.label_maps import label_map_request


def test_get_filament_presets(client):
    """GET /api/v2/filament-presets returns preset list."""
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert [p["name"] for p in data["presets"]] == ["bambu_cmywk", "bambu_cmyw", "clear_cmyg", "clear_cmyw"]
    assert [p["display_name"] for p in data["presets"]] == ["Bambu CMYWK", "Bambu CMYW", "Clear CMYG", "Clear CMYW"]


def test_get_filament_presets_exposes_only_material_inputs(client):
    response = client.get("/api/v2/filament-presets")
    assert response.status_code == 200
    for preset in response.json()["presets"]:
        expected = get_preset(preset["name"])
        assert len(preset["colors"]) == len(expected)
        for color, config in zip(preset["colors"], expected):
            assert set(color) == {"name", "hex", "transmission_distance"}
            assert color["name"] == config.name
            assert color["hex"] == config.hex
            assert color["transmission_distance"] == pytest.approx(config.transmission_distance)


def test_get_filament_presets_defaults_preserve_distinct_layer_heights(client):
    data = client.get("/api/v2/filament-presets").json()
    assert data["defaults"]["backing_layers"] == 3
    assert data["defaults"]["regular_layer_height_mm"] == 0.08
    assert data["defaults"]["transparent_layer_height_mm"] == 0.84
    assert data["defaults"]["max_model_cells"] == settings.max_model_cells
    assert data["defaults"]["max_model_side_px"] == MAX_PROCESSING_DIMENSION
    assert data["defaults"]["max_color_layers"] == MAX_COLOR_LAYERS
    assert data["defaults"]["max_target_colors"] == settings.max_target_colors
    assert data["transparency"]["aggregation"] == "mean"
    threshold = data["transparency"]["td_threshold_mm"]
    assert threshold > 0
    classifications = {}
    for preset in data["presets"]:
        colors = Colors.from_configs([ColorConfig(**color) for color in preset["colors"]])
        mean_td = np.mean([np.mean(color.td_channels) for color in colors.colors.values()])
        classifications[preset["name"]] = is_translucent_set(colors)
        assert classifications[preset["name"]] == (mean_td >= threshold)
    assert classifications["clear_cmyg"]
    assert classifications["clear_cmyw"]


def test_get_filament_presets_cmyw_excludes_black(client):
    data = client.get("/api/v2/filament-presets").json()
    cmyw = next(preset for preset in data["presets"] if preset["name"] == "bambu_cmyw")
    assert len(cmyw["colors"]) == 4
    assert not any(color["name"] == "Key" for color in cmyw["colors"])


def _custom_materials(cyan_td):
    return [
        {"name": "Cyan", "hex": "#3D79C6", "transmission_distance": cyan_td},
        {"name": "Magenta", "hex": "#B3356E", "transmission_distance": 0.52},
        {"name": "Yellow", "hex": "#FFE665", "transmission_distance": 0.58},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 0.61},
    ]


def _resolve_custom(cyan_td):
    return get_colors_from_request(None, [FilamentColorConfig(**c) for c in _custom_materials(cyan_td)])


def test_scalar_and_equal_channel_td_have_identical_predictions():
    scalar = _resolve_custom(0.49)
    channels = _resolve_custom([0.49, 0.49, 0.49])
    codes = ["CMYW", "WCYM", "CYMW", "CCCC"]
    assert scalar["C"].td == 0.49
    assert channels["C"].td_channels == (0.49, 0.49, 0.49)
    assert colors_key(scalar) == colors_key(channels)
    np.testing.assert_allclose(
        codes_to_rgb_batch(codes, 0.08, colors_key(scalar)),
        codes_to_rgb_batch(codes, 0.08, colors_key(channels)),
        rtol=0, atol=1e-12,
    )


def test_distinct_channel_td_reaches_prediction_without_scalar_collapse():
    channels = _resolve_custom([0.2, 0.7, 1.3])
    assert channels["C"].td_channels == (0.2, 0.7, 1.3)
    np.testing.assert_allclose(channels["C"].transmission(0.08), 10 ** (-0.08 / np.array([0.2, 0.7, 1.3])))
    scalar = _resolve_custom(0.7)
    assert not np.allclose(
        codes_to_rgb_batch(["CCCC"], 0.08, colors_key(channels)),
        codes_to_rgb_batch(["CCCC"], 0.08, colors_key(scalar)),
    )


@pytest.mark.parametrize("field,value", [
    ("alpha", 8.08), ("k", 3.49), ("k_rgb", [1, 2, 3]),
    ("td_scale", 1.48), ("td_gamma", 0.2), ("td_rgb", [1, 2, 3]),
])
def test_removed_material_fields_are_rejected_by_api(client, field, value):
    custom = _custom_materials(0.49)
    custom[0][field] = value
    response = client.post("/api/v2/print-settings", json={
        "layerHeight": 0.08, "pixelSize": 0.08, "layerCount": 4,
        "imageDimensions": {"width": 4, "height": 4}, "filamentColors": custom,
    })
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(error["type"] == "extra_forbidden" and error["loc"][-1] == field for error in errors)


def test_v2_stl_with_default_colors(client, sample_color_blocks_with_hex):
    """V2 STL with no preset or custom colors uses default CMYWK."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "filamentPreset": "bambu_cmyw",
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_get_colors_from_request_defaults_to_cmywk():
    colors = get_colors_from_request(None, None)
    expected = get_preset("bambu_cmywk")
    assert colors.get_labels() == [config.label for config in expected]
    for config in expected:
        assert colors[config.label].hex == config.hex
        assert colors[config.label].td == config.transmission_distance


def test_v2_stl_with_bambu_preset(client, sample_color_blocks_with_hex):
    """V2 STL with bambu_cmyw preset works."""
    response = client.post(
        "/api/v2/download-stl",
        json={
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "filamentPreset": "bambu_cmyw",
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
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
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
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
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
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "filamentColors": duplicates,
        },
    )
    assert response.status_code == 422
def test_v2_svg_stl_success(client):
    """V2 SVG STL endpoint works."""
    vector_results = [
        {
            "color": [255, 0, 0],
            "regions": [{"outer": [[0, 0], [10, 0], [10, 10], [0, 10]], "holes": []}],
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
            "filamentPreset": "bambu_cmyw",
        },
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(BytesIO(response.content))
    assert len(zf.namelist()) > 0


def test_v2_svg_download_rejects_obsolete_polygons(client):
    response = client.post(
        "/api/v2/download-svg-stl",
        json={
            "vectorResults": [{
                "color": [255, 0, 0],
                "regions": [{"outer": [[0, 0], [3, 0], [3, 3], [0, 3]], "holes": []}],
                "polygons": [[[0, 0], [3, 0], [3, 3], [0, 3]]],
                "pixel_count": 9,
                "polygon_points": 4,
            }],
            "layerHeight": 0.08,
            "pixelSize": 0.2,
            "layerCount": 4,
            "imageDimensions": {"width": 4, "height": 4},
            "filamentPreset": "bambu_cmyw",
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize('route,generator', [
    ('download-svg-stl', 'generate_svg_stl_zip'),
    ('download-svg-3mf', 'generate_svg_3mf'),
])
def test_svg_download_forwards_082mm_detail_size(client, monkeypatch, route, generator):
    from api.routes import download_v2

    observed = []

    def capture(**kwargs):
        observed.append(kwargs)
        return b'geometry'

    monkeypatch.setattr(download_v2, generator, capture)
    response = client.post(f'/api/v2/{route}', json={
        'vectorResults': [{
            'color': [255, 0, 0],
            'regions': [{'outer': [[0, 0], [3, 0], [3, 3], [0, 3]], 'holes': []}],
            'pixel_count': 16,
            'polygon_points': 4,
        }],
        'layerHeight': 0.08,
        'pixelSize': 0.2,
        'detailSize': 0.82,
        'layerCount': 4,
        'whiteBackingLayers': 0,
        'backingMode': 'black',
        'imageDimensions': {'width': 4, 'height': 4},
        'filamentPreset': 'bambu_cmyw',
    })
    assert response.status_code == 200, response.text
    assert observed[0]['detail_size'] == 0.82
    assert observed[0]['white_backing_layers'] == 0
    assert observed[0]['backing_mode'] == 'black'


# -- 3MF endpoint tests --

def test_v2_3mf_with_default_colors(client, sample_color_blocks_with_hex):
    """V2 3MF with default colors returns valid 3MF file."""
    response = client.post(
        "/api/v2/download-3mf",
        json={
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
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
            **label_map_request(sample_color_blocks_with_hex, 4, 4),
            "layerHeight": 0.08,
            "pixelSize": 0.08,
            "layerCount": 4,
            "filamentPreset": "bambu_cmyw",
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
            "filamentPreset": "bambu_cmyw",
        },
    )
    assert response.status_code == 200
    assert "print_settings.json" in response.headers.get("content-disposition", "")
    data = json.loads(response.content)
    assert data["version"] == "1.0"
    assert data["filament"]["preset"] == "bambu_cmyw"
    assert data["filament"]["extruder_count"] == 4
    assert data["object_dimensions"]["width_mm"] == 10.0
    assert data["object_dimensions"]["height_mm"] == 8.0
    cyan = next(e for e in data["filament"]["extruders"] if e["name"] == "Cyan")
    assert set(cyan) == {"index", "name", "color", "transmission_distance"}
    assert cyan["transmission_distance"] == pytest.approx(get_preset("bambu_cmyw")[0].transmission_distance)


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
    """Print settings with no preset or custom uses default CMYWK."""
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
    assert data["filament"]["preset"] == "bambu_cmywk"


def test_palette_and_preset_materials_match(client):
    presets = client.get("/api/v2/filament-presets").json()["presets"]
    for preset in presets:
        palette = client.get(f"/api/palettes/{preset['name']}")
        assert palette.status_code == 200
        assert palette.json()["colors"] == preset["colors"]


@pytest.mark.parametrize("layer_height,preset,slicer_height,slices", [
    (0.08, "bambu_cmyw", 0.08, 1),
    (0.84, "clear_cmyw", 0.28, 3),
])
@pytest.mark.parametrize("export_type", ["stl", "3mf"])
def test_download_geometry_and_settings_agree_on_color_and_backing_height(
    client, sample_color_blocks_with_hex, layer_height, preset, slicer_height, slices, export_type,
):
    body = {
        "layerHeight": layer_height, "pixelSize": 0.08, "layerCount": 4,
        "imageDimensions": {"width": 4, "height": 4}, "filamentPreset": preset,
    }
    response = client.post(f"/api/v2/download-{export_type}", json={
        **body, **label_map_request(sample_color_blocks_with_hex, 4, 4),
    })
    assert response.status_code == 200
    if export_type == "3mf":
        scene = trimesh.load(BytesIO(response.content), file_type="3mf")
        z_min, z_max = scene.bounds[:, 2]
    else:
        archive = zipfile.ZipFile(BytesIO(response.content))
        stls = [name for name in archive.namelist() if name.endswith(".stl")]
        assert stls
        z = []
        for name in stls:
            data = archive.read(name)
            triangle_count = struct.unpack_from("<I", data, 80)[0]
            assert len(data) == 84 + triangle_count * 50
            for triangle in struct.iter_unpack("<12fH", data[84:]):
                z.extend((triangle[5], triangle[8], triangle[11]))
        z_min, z_max = min(z), max(z)
    assert z_min == pytest.approx(0.0, abs=1e-6)
    assert z_max == pytest.approx(7 * layer_height, abs=1e-6)

    settings_response = client.post("/api/v2/print-settings", json=body)
    assert settings_response.status_code == 200
    settings = settings_response.json()
    assert settings["print_settings"]["backing_color_layer_count"] == 3
    assert settings["print_settings"]["layer_height"] == pytest.approx(slicer_height)
    assert settings["print_settings"]["color_layer_height_mm"] == layer_height
    assert settings["print_settings"]["slicer_layers_per_color_layer"] == slices
    assert settings["object_dimensions"]["total_layer_count"] == 7 * slices
    assert settings["object_dimensions"]["total_height_mm"] == pytest.approx(z_max - z_min)


def test_print_settings_preserves_distinct_custom_td_channels(client):
    response = client.post("/api/v2/print-settings", json={
        "layerHeight": 0.08, "pixelSize": 0.08, "layerCount": 4,
        "imageDimensions": {"width": 4, "height": 4},
        "filamentColors": _custom_materials([0.2, 0.7, 1.3]),
    })
    assert response.status_code == 200
    extruders = response.json()["filament"]["extruders"]
    assert extruders[0]["transmission_distance"] == [0.2, 0.7, 1.3]
    assert extruders[1]["transmission_distance"] == 0.52
    assert all(set(e) == {"index", "name", "color", "transmission_distance"} for e in extruders)



def test_filament_preview_uses_default_three_layer_backing_in_predictions(client):
    custom = _custom_materials([0.2, 0.7, 1.3])
    body = {"filamentColors": custom, "layerCount": 2, "layerHeight": 0.08}
    response = client.post("/api/filament-preview", json=body)
    assert response.status_code == 200
    entries = {entry["code"]: entry["rgb"] for entry in response.json()["colorMatrix"]}
    colors = _resolve_custom([0.2, 0.7, 1.3])
    expected = codes_to_rgb_batch(["CCWWW"], 0.08, colors_key(colors), background_rgb=(255, 255, 255))[0]
    assert entries["CC"] == np.round(expected).astype(int).tolist()

    unbacked = client.post("/api/filament-preview", json={**body, "whiteBackingLayers": 0})
    assert unbacked.status_code == 200
    unbacked_entries = {entry["code"]: entry["rgb"] for entry in unbacked.json()["colorMatrix"]}
    expected_unbacked = codes_to_rgb_batch(["CC"], 0.08, colors_key(colors))[0]
    assert unbacked_entries["CC"] == np.round(expected_unbacked).astype(int).tolist()
    assert entries["CC"] != unbacked_entries["CC"]



def test_layer_limit_endpoint_reports_the_filament_set_maximum(client):
    response = client.post("/api/v2/layer-limit", json={"filamentPreset": "bambu_cmywk"})
    assert response.status_code == 200
    assert 1 <= response.json()["maxLayerCount"] <= MAX_COLOR_LAYERS
