"""
QA Round 19: Tests for edge cases and potential bugs found in R19

This test file covers:
1. code_to_rgb type inconsistency between empty string and whitespace
2. combined_permutation_matrix accepts count=0 and count=1
3. print_settings_generator accepts empty filament_colors
"""
import pytest
import json
import numpy as np

from core.blend_color import BlendTestGenerator, Colors
from core.color_config import ColorConfig
from services.print_settings_generator import generate_print_settings


class TestCodeToRgbTypeConsistency:
    """Test code_to_rgb returns consistent types for all inputs."""

    @pytest.fixture
    def generator(self):
        """Create a BlendTestGenerator with standard CMYK colors."""
        colors = Colors.from_configs([
            ColorConfig(name='Cyan', hex='#00FFFF', transmission_distance=3.0),
            ColorConfig(name='Magenta', hex='#FF00FF', transmission_distance=3.0),
            ColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=3.0),
            ColorConfig(name='White', hex='#FFFFFF', transmission_distance=3.0),
        ])
        return BlendTestGenerator(colors=colors)

    def test_code_to_rgb_empty_string_type(self, generator):
        """
        QA-177: code_to_rgb returns int tuple for empty string.

        Empty string '' returns (255, 255, 255) - tuple of ints.
        This is inconsistent with whitespace handling.
        """
        result = generator.code_to_rgb('')
        # Should return consistent type (all int OR all float)
        assert isinstance(result[0], (int, np.integer)), f"Expected int, got {type(result[0])}"
        assert isinstance(result[1], (int, np.integer)), f"Expected int, got {type(result[1])}"
        assert isinstance(result[2], (int, np.integer)), f"Expected int, got {type(result[2])}"
        assert result == (255, 255, 255)

    def test_code_to_rgb_whitespace_string_type(self, generator):
        """
        QA-177: code_to_rgb returns float tuple for whitespace string.

        Whitespace '  ' returns (255.0, 255.0, 255.0) - tuple of floats.
        This is inconsistent with empty string handling.
        """
        result = generator.code_to_rgb('  ')
        # Check type consistency with empty string
        empty_result = generator.code_to_rgb('')
        # Both should return the same type
        assert type(result[0]) == type(empty_result[0]), \
            f"Type mismatch: empty='{type(empty_result[0])}', whitespace='{type(result[0])}'"
        assert result == empty_result

    def test_code_to_rgb_valid_code_type(self, generator):
        """
        QA-177: Valid codes should return numpy float64, not inconsistent types.
        """
        result = generator.code_to_rgb('C')
        # Valid codes should return numpy floats for consistency
        assert isinstance(result[0], (float, np.floating)), \
            f"Expected float, got {type(result[0])}"

    def test_code_to_rgb_none_type(self, generator):
        """
        QA-177: None input should return same type as empty string.
        """
        result = generator.code_to_rgb(None)
        empty_result = generator.code_to_rgb('')
        # None and empty string should return same type
        assert type(result[0]) == type(empty_result[0]), \
            f"Type mismatch: None='{type(result[0])}', empty='{type(empty_result[0])}'"


class TestCombinedPermutationMatrixValidation:
    """Test combined_permutation_matrix edge cases."""

    @pytest.fixture
    def generator(self):
        """Create a BlendTestGenerator with standard colors."""
        colors = Colors.from_configs([
            ColorConfig(name='Cyan', hex='#00FFFF', transmission_distance=3.0),
            ColorConfig(name='Magenta', hex='#FF00FF', transmission_distance=3.0),
            ColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=3.0),
            ColorConfig(name='White', hex='#FFFFFF', transmission_distance=3.0),
        ])
        return BlendTestGenerator(colors=colors)

    def test_combined_permutation_matrix_count_zero(self, generator):
        """
        QA-178: combined_permutation_matrix now validates count >= 1.

        count=0 should raise ValueError since "zero layers" is invalid.
        """
        with pytest.raises(ValueError, match="count must be at least 1"):
            generator.combined_permutation_matrix(['C', 'M', 'Y', 'W'], 0)

    def test_combined_permutation_matrix_count_one(self, generator):
        """
        QA-179: combined_permutation_matrix count=1 is valid (single layer).

        count=1 returns (4, 1) matrix with just single-character codes.
        This is intentional - represents single-layer permutations.
        """
        result = generator.combined_permutation_matrix(['C', 'M', 'Y', 'W'], 1)
        # count=1 returns single-character codes only
        assert result.shape == (4, 1)
        assert result.iloc[0, 0] == 'C'

    def test_combined_permutation_matrix_normal_count(self, generator):
        """Verify normal count works as expected."""
        result = generator.combined_permutation_matrix(['C', 'M', 'Y', 'W'], 3)
        # Should have 4 rows (one per color)
        assert result.shape[0] == 4
        # Should have columns for combos of length 1 to 3
        # row 0: C, CC, CMC, CMCM (1 + 1 + 4 = 6)


class TestPrintSettingsEmptyFilamentColors:
    """Test print_settings_generator edge cases."""

    def test_print_settings_empty_filament_colors(self):
        """
        QA-180: print_settings_generator now validates non-empty filament_colors.

        Empty filament_colors should raise ValueError since 0 extruders is invalid.
        """
        with pytest.raises(ValueError, match="must contain at least 1 color"):
            generate_print_settings(
                layer_height=0.2,
                pixel_size=0.08,
                layer_count=4,
                image_dimensions={'width': 100, 'height': 100},
                filament_colors=[],
            )

    def test_print_settings_with_valid_filament_colors(self):
        """Verify normal filament colors work correctly."""
        result = generate_print_settings(
            layer_height=0.2,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 100, 'height': 100},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#00FFFF', 'transmission_distance': 3.0},
                {'name': 'Magenta', 'hex': '#FF00FF', 'transmission_distance': 3.0},
                {'name': 'Yellow', 'hex': '#FFFF00', 'transmission_distance': 3.0},
                {'name': 'White', 'hex': '#FFFFFF', 'transmission_distance': 3.0},
            ],
        )
        data = json.loads(result)
        assert data['filament']['extruder_count'] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
