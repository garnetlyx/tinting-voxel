"""
Unit tests for print settings generator service.
"""
import json

import pytest

from services.print_settings_generator import generate_print_settings


class TestGeneratePrintSettings:
    """Tests for generate_print_settings function."""

    def test_basic_output_structure(self):
        """Output contains all expected top-level keys."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 100, 'height': 80},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
                {'name': 'Magenta', 'hex': '#EC008C', 'transmission_distance': 1.9},
                {'name': 'Yellow', 'hex': '#F4EE2A', 'transmission_distance': 2.5},
                {'name': 'White', 'hex': '#FFFFFF', 'transmission_distance': 7.2},
            ],
        )
        data = json.loads(result)
        assert data['version'] == '1.0'
        assert data['generator'] == 'tinting-voxel'
        assert 'print_settings' in data
        assert 'object_dimensions' in data
        assert 'filament' in data

    def test_print_settings_values(self):
        """Print settings reflect input parameters."""
        result = generate_print_settings(
            layer_height=0.12,
            pixel_size=0.08,
            layer_count=6,
            image_dimensions={'width': 50, 'height': 40},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
        )
        data = json.loads(result)
        ps = data['print_settings']
        assert ps['layer_height'] == 0.12
        assert ps['color_layer_count'] == 6
        assert ps['backing_color_layer_count'] == 3
        assert ps['color_layer_height_mm'] == 0.12
        assert ps['slicer_layers_per_color_layer'] == 1

    def test_object_dimensions_calculation(self):
        """Object dimensions are correctly computed from pixels and pixel_size."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 100, 'height': 80},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
        )
        data = json.loads(result)
        dims = data['object_dimensions']
        assert dims['width_mm'] == 10.0   # 100 * 0.1
        assert dims['height_mm'] == 8.0   # 80 * 0.1
        assert dims['total_height_mm'] == 0.56
        assert dims['total_layer_count'] == 7
        assert dims['optical_layer_count'] == 4
        assert dims['width_pixels'] == 100
        assert dims['height_pixels'] == 80
        assert dims['pixel_size_mm'] == 0.1
    def test_filament_extruders(self):
        """Filament section lists all extruders with correct info."""
        colors = [
            {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            {'name': 'Magenta', 'hex': '#EC008C', 'transmission_distance': 1.9},
            {'name': 'Yellow', 'hex': '#F4EE2A', 'transmission_distance': 2.5},
            {'name': 'White', 'hex': '#FFFFFF', 'transmission_distance': 7.2},
        ]
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=colors,
            filament_preset='bambu_cmyw',
        )
        data = json.loads(result)
        filament = data['filament']
        assert filament['preset'] == 'bambu_cmyw'
        assert filament['extruder_count'] == 4
        assert len(filament['extruders']) == 4
        assert filament['extruders'][0]['index'] == 0
        assert filament['extruders'][0]['name'] == 'Cyan'
        assert filament['extruders'][0]['color'] == '#0086D6'
        assert filament['extruders'][0]['transmission_distance'] == 3.0
        assert filament['extruders'][3]['name'] == 'White'

    def test_no_preset_sets_null(self):
        """Preset is null when not provided."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Red', 'hex': '#FF0000', 'transmission_distance': 2.0},
            ],
        )
        data = json.loads(result)
        assert data['filament']['preset'] is None

    def test_output_is_valid_json(self):
        """Output is parseable JSON with proper indentation."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
        )
        # Should not raise
        data = json.loads(result)
        assert isinstance(data, dict)
        # Should be indented (multi-line)
        assert '\n' in result
    def test_explicit_zero_white_backing(self):
        """Explicitly disabling backing removes it from the reported stack."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
            white_backing_layers=0,
        )
        data = json.loads(result)
        assert data['print_settings']['backing_color_layer_count'] == 0
        assert data['object_dimensions']['total_layer_count'] == 4
        assert data['object_dimensions']['total_height_mm'] == 0.32


    def test_transparent_color_height_is_three_slicer_layers(self):
        data = json.loads(generate_print_settings(
            layer_height=0.84, pixel_size=0.1, layer_count=4,
            image_dimensions={"width": 10, "height": 10},
            filament_colors=[{"name": "Cyan", "hex": "#5489B4", "transmission_distance": [2.0, 4.0, 8.0]}],
        ))
        settings = data["print_settings"]
        assert settings["color_layer_height_mm"] == 0.84
        assert settings["layer_height"] == pytest.approx(0.28)
        assert settings["slicer_layers_per_color_layer"] == 3
        assert settings["backing_color_layer_count"] == 3
        assert data["object_dimensions"]["total_height_mm"] == pytest.approx(5.88)
        assert data["filament"]["extruders"][0]["transmission_distance"] == [2.0, 4.0, 8.0]


@pytest.mark.parametrize("height", [0.08, 0.84, 0.85, 0.12345])
def test_slicer_counts_and_color_counts_have_explicit_units(height):
    data = json.loads(generate_print_settings(
        layer_height=height, pixel_size=0.1, layer_count=4,
        image_dimensions={"width": 1, "height": 1},
        filament_colors=[{"name": "Cyan", "hex": "#5489B4", "transmission_distance": 2.0}],
    ))
    settings, dimensions = data["print_settings"], data["object_dimensions"]
    slices = settings["slicer_layers_per_color_layer"]
    assert settings["color_layer_count"] == 4
    assert settings["backing_color_layer_count"] == 3
    assert "layer_count" not in settings and "white_backing_layers" not in settings
    assert dimensions["optical_layer_count"] == 4 * slices
    assert dimensions["backing_layer_count"] == 3 * slices
    assert dimensions["total_layer_count"] == 7 * slices
    assert dimensions["total_height_mm"] == pytest.approx(7 * height)
    assert dimensions["total_height_mm"] == pytest.approx(
        settings["layer_height"] * dimensions["total_layer_count"], abs=1e-12,
    )
