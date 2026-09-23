"""
Integration tests for the /api/filament-preview endpoint.
"""
import base64


def test_filament_preview_default(client):
    """POST /api/filament-preview with bambu preset uses default Bambu CMYW."""
    response = client.post("/api/filament-preview", json={"filamentPreset": "bambu_cmyw"})
    assert response.status_code == 200
    data = response.json()
    assert "image" in data
    assert "colorMatrix" in data
    assert "stats" in data
    assert "imageDimensions" in data
    assert "warnings" in data
    assert data["stats"]["colorCount"] == 4
    assert data["stats"]["combinationCount"] == 256


def test_filament_preview_with_bambu_preset(client):
    """POST /api/filament-preview with bambu_cmyw preset."""
    response = client.post(
        "/api/filament-preview",
        json={"filamentPreset": "bambu_cmyw"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["colorCount"] == 4
    assert len(data["warnings"]) == 0


def test_filament_preview_with_clear_preset(client):
    """POST /api/filament-preview with clear_cmyw preset."""
    response = client.post(
        "/api/filament-preview",
        json={"filamentPreset": "clear_cmyw"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["colorCount"] == 4


def test_filament_preview_with_custom_colors(client):
    """POST /api/filament-preview with custom 4-color config."""
    custom_colors = [
        {"name": "Red", "hex": "#FF0000", "transmission_distance": 2.0},
        {"name": "Green", "hex": "#00FF00", "transmission_distance": 3.0},
        {"name": "Blue", "hex": "#0000FF", "transmission_distance": 1.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.0},
    ]
    response = client.post(
        "/api/filament-preview",
        json={"filamentColors": custom_colors},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["colorCount"] == 4
    assert data["stats"]["combinationCount"] == 256


def test_filament_preview_with_6_colors(client):
    """POST /api/filament-preview with 6-color config."""
    colors = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#FF00FF", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
        {"name": "Black", "hex": "#000000", "transmission_distance": 0.5},
        {"name": "Red", "hex": "#FF0000", "transmission_distance": 2.0},
    ]
    response = client.post(
        "/api/filament-preview",
        json={"filamentColors": colors},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["colorCount"] == 6
    assert data["stats"]["combinationCount"] == 1296


def test_filament_preview_returns_valid_base64_png(client):
    """Preview image is a valid base64-encoded PNG."""
    response = client.post("/api/filament-preview", json={"filamentPreset": "bambu_cmyw"})
    assert response.status_code == 200
    data = response.json()
    decoded = base64.b64decode(data["image"])
    assert decoded[:4] == b'\x89PNG'


def test_filament_preview_custom_layer_count(client):
    """Preview with custom layer count changes combination count."""
    response = client.post(
        "/api/filament-preview",
        json={"filamentPreset": "bambu_cmyw", "layerCount": 3},
    )
    assert response.status_code == 200
    data = response.json()
    # 4 colors, 3 layers = 4^3 = 64 combinations
    assert data["stats"]["combinationCount"] == 64


def test_filament_preview_too_few_colors_returns_422(client):
    """Preview with only 3 custom colors returns 422."""
    too_few = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#FF00FF", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
    ]
    response = client.post(
        "/api/filament-preview",
        json={"filamentColors": too_few},
    )
    assert response.status_code == 422


def test_filament_preview_duplicate_labels_returns_422(client):
    """Preview with duplicate first-letter labels returns 422."""
    duplicates = [
        {"name": "Cyan", "hex": "#00FFFF", "transmission_distance": 3.0},
        {"name": "Crimson", "hex": "#DC143C", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
    ]
    response = client.post(
        "/api/filament-preview",
        json={"filamentColors": duplicates},
    )
    assert response.status_code == 422


def test_filament_preview_invalid_hex_returns_422(client):
    """Preview with invalid hex color returns 422."""
    invalid = [
        {"name": "Cyan", "hex": "#ZZZZZZ", "transmission_distance": 3.0},
        {"name": "Magenta", "hex": "#FF00FF", "transmission_distance": 1.9},
        {"name": "Yellow", "hex": "#FFFF00", "transmission_distance": 2.5},
        {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
    ]
    response = client.post(
        "/api/filament-preview",
        json={"filamentColors": invalid},
    )
    assert response.status_code == 422


def test_filament_preview_no_preset_or_colors_returns_422(client):
    """POST /api/filament-preview with neither preset nor colors returns 422."""
    response = client.post("/api/filament-preview", json={})
    assert response.status_code == 422


def test_filament_preview_color_matrix_structure(client):
    """Color matrix entries have correct structure."""
    response = client.post("/api/filament-preview", json={"filamentPreset": "bambu_cmyw"})
    assert response.status_code == 200
    data = response.json()
    matrix = data["colorMatrix"]
    assert len(matrix) == 256  # 4^4
    for entry in matrix:
        assert "code" in entry
        assert "rgb" in entry
        assert len(entry["code"]) == 4  # 4 layer codes
        assert len(entry["rgb"]) == 3
        for v in entry["rgb"]:
            assert 0 <= v <= 255
