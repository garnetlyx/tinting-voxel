"""Real API defaults follow material TD; explicit physical heights are preserved."""
import io
import json
import struct
import zipfile

import pytest


def _custom(td):
    return [
        {"name": name, "hex": color, "transmission_distance": td}
        for name, color in [("Cyan", "#0099FF"), ("Magenta", "#FF0099"),
                            ("Yellow", "#FFFF00"), ("White", "#FFFFFF")]
    ]


@pytest.mark.parametrize("material,height,expected", [
    ({"filamentPreset": "clear_cmyw"}, None, .84),
    ({"filamentPreset": "clear_cmyg"}, None, .84),
    ({"filamentPreset": "bambu_cmyw"}, None, .08),
    ({"filamentColors": _custom([.1, 6.85, 6.85])}, None, .84),
    ({"filamentColors": _custom([.1, 6.5, 6.5])}, None, .08),
    ({"filamentColors": _custom(4.6)}, None, .84),
    ({"filamentPreset": "clear_cmyw"}, .08, .08),
    ({"filamentPreset": "bambu_cmyw"}, .84, .84),
    ({"filamentPreset": "clear_cmyw"}, .12, .12),
])
def test_settings_height_uses_material_values_only_when_omitted(client, material, height, expected):
    body = {**material, "pixelSize": .1, "layerCount": 4,
            "imageDimensions": {"width": 2, "height": 2}}
    if height is not None:
        body["layerHeight"] = height
    response = client.post("/api/v2/print-settings", json=body)
    assert response.status_code == 200, response.text
    settings = response.json()
    assert settings["print_settings"]["color_layer_height_mm"] == pytest.approx(expected)
    dims = settings["object_dimensions"]
    assert dims["total_height_mm"] == pytest.approx(7 * expected)
    assert settings["print_settings"]["layer_height"] * dims["total_layer_count"] == pytest.approx(7 * expected)


def test_real_preview_and_simulation_match_explicit_transparent_height(client, sample_color_blocks_with_hex):
    common = {"filamentPreset": "clear_cmyw", "layerCount": 2}
    default = client.post("/api/filament-preview", json=common)
    explicit = client.post("/api/filament-preview", json={**common, "layerHeight": .84})
    assert default.status_code == explicit.status_code == 200
    assert default.json()["colorMatrix"] == explicit.json()["colorMatrix"]
    body = {**common, "colorBlocks": sample_color_blocks_with_hex,
            "imageDimensions": {"width": 4, "height": 4}}
    default = client.post("/api/simulate-preview", json=body)
    explicit = client.post("/api/simulate-preview", json={**body, "layerHeight": .84})
    assert default.status_code == explicit.status_code == 200
    assert default.json() == explicit.json()
    assert default.json()["printStack"]["totalHeightMm"] == pytest.approx(5 * .84)


@pytest.mark.parametrize("mode", ["pixel", "svg"])
def test_process_image_uses_transparent_default(client, tiny_png_bytes, mode):
    response = client.post("/api/process-image", data={
        "filamentPreset": "clear_cmyw", "layerCount": "2", "mode": mode,
        "pixelSize": ".42", "minArea": ".01", "numColors": "4",
    }, files={"image": ("sample.png", tiny_png_bytes, "image/png")})
    assert response.status_code == 200, response.text
    assert response.json()["printStack"]["totalHeightMm"] == pytest.approx(5 * .84)


@pytest.mark.parametrize("route,generator,vector", [
    ("download-stl", "generate_stl_zip", False),
    ("download-3mf", "generate_3mf", False),
    ("download-svg-stl", "generate_svg_stl_zip", True),
    ("download-svg-3mf", "generate_svg_3mf", True),
])
def test_every_export_forwards_resolved_height_once(client, monkeypatch, sample_color_blocks_with_hex, route, generator, vector):
    import api.filament_payload as filament_payload
    from api.routes import download_v2

    captured = []
    parsed = []
    original = filament_payload.get_colors_from_request

    def resolve(*args):
        colors = original(*args)
        parsed.append(colors)
        return colors

    def generate(**kwargs):
        captured.append(kwargs)
        return b"export"

    monkeypatch.setattr(filament_payload, "get_colors_from_request", resolve)
    monkeypatch.setattr(download_v2, generator, generate)
    body = {"filamentPreset": "clear_cmyw", "layerCount": 2, "pixelSize": .42,
            "imageDimensions": {"width": 4, "height": 4}}
    if vector:
        body["vectorResults"] = [{"color": [255, 0, 0], "pixel_count": 4,
                                  "polygon_points": 4, "regions": [{"outer": [[0, 0], [2, 0], [2, 2], [0, 2]], "holes": []}]}]
    else:
        body["colorBlocks"] = sample_color_blocks_with_hex
    response = client.post(f"/api/v2/{route}", json=body)
    assert response.status_code == 200, response.text
    assert len(parsed) == len(captured) == 1
    assert captured[0]["colors"] is parsed[0]
    assert captured[0]["layer_height"] == pytest.approx(.84)


def test_real_batch_export_uses_transparent_default(client, tiny_png_bytes):
    response = client.post("/api/batch/download-stl", data={
        "filamentPreset": "clear_cmyw", "layerCount": "2", "pixelSize": ".42",
    }, files=[("images", ("sample.png", tiny_png_bytes, "image/png"))])
    assert response.status_code == 200, response.text
    outer = zipfile.ZipFile(io.BytesIO(response.content))
    heights = []
    for name in outer.namelist():
        content = outer.read(name)
        archives = [zipfile.ZipFile(io.BytesIO(content))] if name.endswith('.zip') else []
        stls = [(name, content)] if name.endswith('.stl') else []
        for archive in archives:
            stls.extend((n, archive.read(n)) for n in archive.namelist() if n.endswith('.stl'))
        for _, data in stls:
            for triangle in struct.iter_unpack('<12fH', data[84:]):
                heights.extend((triangle[5], triangle[8], triangle[11]))
    assert heights
    assert max(heights) - min(heights) == pytest.approx(5 * .84, abs=1e-6)


def test_param_search_uses_same_omitted_height_resolution(client, monkeypatch, tiny_png_bytes):
    from api.routes import param_search
    captured = []

    class Service:
        def __init__(self, config):
            captured.append(config)

        def total_candidates(self):
            return 1

        def run(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(param_search, "ParamSearchService", Service)
    response = client.post("/api/param-search", data={
        "filamentColors": json.dumps(_custom([.1, 6.85, 6.85])), "n_trials": "1",
    }, files={"image": ("sample.png", tiny_png_bytes, "image/png")})
    assert response.status_code == 200, response.text
    assert captured[0].fixed.layer_height == pytest.approx(.84)
