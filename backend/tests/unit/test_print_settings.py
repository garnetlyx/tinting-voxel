"""
Unit tests for print settings generator service.
"""
import json

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
            base_plate_thickness=0.5,
        )
        data = json.loads(result)
        ps = data['print_settings']
        assert ps['layer_height'] == 0.12
        assert ps['layer_count'] == 6
        assert ps['white_backing_layers'] == 1
        assert ps['base_plate_thickness'] == 0.5

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
        assert dims['total_height_mm'] == 0.4  # 4 optical + 1 backing
        assert dims['total_layer_count'] == 5
        assert dims['optical_layer_count'] == 4
        assert dims['width_pixels'] == 100
        assert dims['height_pixels'] == 80
        assert dims['pixel_size_mm'] == 0.1

    def test_object_dimensions_with_base_plate(self):
        """Total height includes base plate thickness."""
        result = generate_print_settings(
            layer_height=0.1,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
            base_plate_thickness=0.5,
        )
        data = json.loads(result)
        assert data['object_dimensions']['total_height_mm'] == 1.0  # 4 optical + 1 backing + 0.5 base

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
            filament_preset='bambu_cmyk',
        )
        data = json.loads(result)
        filament = data['filament']
        assert filament['preset'] == 'bambu_cmyk'
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

    def test_zero_base_plate(self):
        """Zero base plate thickness is included correctly."""
        result = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.1,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#0086D6', 'transmission_distance': 3.0},
            ],
            base_plate_thickness=0.0,
        )
        data = json.loads(result)
        assert data['print_settings']['base_plate_thickness'] == 0.0

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
        assert data['print_settings']['white_backing_layers'] == 0
        assert data['object_dimensions']['total_layer_count'] == 4
        assert data['object_dimensions']['total_height_mm'] == 0.32
