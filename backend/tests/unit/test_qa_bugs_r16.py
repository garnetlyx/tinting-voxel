"""
QA Round 16: Tests for edge cases and potential bugs found in R16

This test file covers:
1. Duplicate labels with different casing (case-insensitive check)
2. BlendTestGenerator with invalid layer_count values
3. Colors class case-insensitive label lookup
4. compute_reference_matrices with layer_count=0
5. generate_box with negative coordinate ranges
6. Empty Colors edge cases
"""
import pytest
import numpy as np

from api.models import FilamentColorConfig, FilamentConfigMixin
from api.models import DownloadSTLRequestV2, FilamentPreset, ImageDimensions
from config.print_defaults import DEFAULT_FILAMENT_PRESET
from core.blend_color import Colors, Color, BlendTestGenerator
from core.color_config import ColorConfig, get_preset
from services.stl_generator import compute_reference_matrices, generate_box


class TestDuplicateLabelsCaseInsensitive:
    """Test that duplicate labels with different casing are rejected."""

    def test_filament_color_config_case_insensitive_duplicate(self):
        """
        QA-160: FilamentColorConfig validator accepts labels 'C' and 'c' as distinct.
        The label is derived from name[0].upper(), so 'Cyan' and 'cyan' both
        produce label 'C', creating a duplicate label bug.
        """
        # Create two colors with same label but different casing
        config1 = FilamentColorConfig(name='Cyan', hex='#00FFFF', transmission_distance=3.0)
        config2 = FilamentColorConfig(name='cyan', hex='#00FFFF', transmission_distance=3.0)

        # Both produce label 'C' due to .upper() in label property
        assert config1.label == 'C'
        assert config2.label == 'C'

        # This should fail validation but currently doesn't
        # The validator checks unique_labels but it's case-sensitive
        # because it uses c.name[0].upper() but labels list may have duplicates
        with pytest.raises(ValueError, match="unique.*first letters"):
            DownloadSTLRequestV2(
                filamentColors=[
                    config1,
                    config2,
                    FilamentColorConfig(name='Magenta', hex='#FF00FF', transmission_distance=1.9),
                    FilamentColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=2.5),
                ],
                colorBlocks=[],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions=ImageDimensions(width=100, height=100)
            )


class TestBlendTestGeneratorEdgeCases:
    """Test BlendTestGenerator with edge case inputs."""

    def test_blend_test_generator_with_zero_layer_count(self):
        """
        QA-161: BlendTestGenerator rejects layer_count_max=0 with validation error.
        Fixed: Added validation to reject zero or negative layer_count_max.
        """
        colors = Colors()
        # Should reject layer_count_max=0
        with pytest.raises(ValueError, match="layer_count_max must be positive"):
            BlendTestGenerator(colors=colors, layer_count_max=0)

    def test_blend_test_generator_with_negative_layer_count(self):
        """
        QA-162: BlendTestGenerator rejects negative layer_count_max with validation error.
        Fixed: Added validation to reject zero or negative layer_count_max.
        """
        colors = Colors()
        # Should reject negative layer_count_max
        with pytest.raises(ValueError, match="layer_count_max must be positive"):
            BlendTestGenerator(colors=colors, layer_count_max=-1)

    def test_blend_test_generator_with_none_colors(self):
        """An omitted material set uses the configured default preset."""
        gen = BlendTestGenerator(colors=None, layer_count_max=4)
        assert gen.colors.get_labels() == [c.label for c in get_preset(DEFAULT_FILAMENT_PRESET)]



class TestColorsCaseInsensitiveLookup:
    """Test Colors class label lookup behavior."""

    def test_colors_getitem_case_insensitive(self):
        """
        QA-164: Colors.__getitem__ does case-insensitive lookup which can cause issues.
        Looking up 'c' and 'C' both succeed, but labels should be case-sensitive.
        """
        colors = Colors()

        # Both lookups succeed due to .strip().upper() in __getitem__
        cyan_upper = colors['C']
        cyan_lower = colors['c']

        # This creates ambiguity - users can use lowercase to access colors
        # but the actual labels are uppercase
        # Color.__repr__ returns the name (default colors use label as name)
        assert repr(cyan_upper) == 'C'
        assert repr(cyan_lower) == 'C'

        # Both return the same color object due to case-insensitive lookup
        assert cyan_upper is cyan_lower

        # The issue: if we add a color with lowercase label 'c',
        # it becomes 'C' after normalization, creating a collision
        with pytest.raises(ValueError, match="Duplicate.*label"):
            Colors.from_configs([
                ColorConfig(name='Cyan', hex='#00FFFF', transmission_distance=3.0),
                ColorConfig(name='cyan', hex='#00FFFF', transmission_distance=3.0),
                ColorConfig(name='Magenta', hex='#FF00FF', transmission_distance=2.0),
                ColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=2.5),
            ])


class TestComputeReferenceMatricesEdgeCases:
    """Test compute_reference_matrices with edge case inputs."""

    def test_compute_reference_matrices_with_zero_layer_count(self):
        """
        QA-165: compute_reference_matrices rejects layer_count=0 with validation error.
        Fixed: Added validation to require layer_count >= 1.
        """
        colors = Colors()

        # Should reject layer_count=0
        with pytest.raises(ValueError, match="layer_count must be positive"):
            compute_reference_matrices(
                layer_count=0,
                layer_height=0.08,
                colors=colors
            )

    def test_compute_reference_matrices_excessive_permutations(self, monkeypatch):
        """
        QA-166: compute_reference_matrices rejects enumeration that the
        probe-extrapolated cost puts over the time budget. 4^8 (65,536 codes,
        ~1s even under load) is comfortably affordable and must pass; an
        8-color x 8-layer opaque set (~16.8M codes) must raise once its
        estimate sits over the budget. The estimate is pinned so the guard
        decision is machine-speed independent.
        """
        from core.color_materials import Color
        # 4 colors x 8 layers fits the budget with margin — no cap, no raise.
        compute_reference_matrices(layer_count=8, layer_height=0.08, colors=Colors())

        big = Colors(colors={
            l: Color(l, 0.5, h) for l, h in zip(
                "ABCDEFGH",
                ["#3D79C6", "#B3356E", "#FFE665", "#FFFFFF",
                 "#112233", "#445566", "#778899", "#0B0F0C"])
        })
        import services.stl_generator as sg
        monkeypatch.setattr(sg, "_estimate_build_seconds", lambda n: 1e9)
        with pytest.raises(ValueError, match="over the .* budget"):
            compute_reference_matrices(
                layer_count=8,  # 8^8 = 16,777,216 codes, hundreds of seconds
                layer_height=0.08,
                colors=big
            )


class TestGenerateBoxNegativeRanges:
    """Test generate_box with negative coordinate ranges."""

    def test_generate_box_with_negative_xrange(self):
        """
        QA-167: generate_box rejects negative coordinate ranges with validation error.
        Fixed: Added validation to require non-negative coordinates.
        """
        # Should reject negative ranges
        with pytest.raises(ValueError, match="All coordinates must be non-negative"):
            generate_box(
                xrange=(-1, 0),  # Negative start
                yrange=(0, 1),
                zrange=(0, 1)
            )

    def test_generate_box_with_inverted_ranges(self):
        """
        QA-168: generate_box rejects inverted ranges (start > end) with validation error.
        Fixed: Added validation to enforce start < end for all ranges.
        """
        # Should validate that start < end
        with pytest.raises(ValueError, match="Range start must be less than end"):
            generate_box(
                xrange=(1, 0),  # Inverted
                yrange=(1, 0),  # Inverted
                zrange=(1, 0)   # Inverted
            )


class TestEmptyColorsEdgeCases:
    """Test empty Colors instance behavior."""

    def test_empty_colors_get_labels(self):
        """
        QA-169: Empty Colors() instance has edge cases in get_labels and __len__.
        """
        colors = Colors(colors={})

        assert len(colors) == 0
        assert colors.get_labels() == []

        # Attempting to compute reference matrices with empty colors
        with pytest.raises(ValueError, match="no colors defined"):
            compute_reference_matrices(
                layer_count=4,
                layer_height=0.08,
                colors=colors
            )

    def test_empty_colors_from_configs(self):
        """
        QA-170: Colors.from_configs with empty list now raises ValueError.
        Updated: Minimum 4 colors required.
        """
        with pytest.raises(ValueError, match="at least 4 colors"):
            Colors.from_configs([])


class TestFilamentConfigMixinValidation:
    """Test FilamentConfigMixin validation behavior."""

    def test_filament_config_mixin_with_both_preset_and_colors(self):
        """
        QA-171: Verify that FilamentConfigMixin rejects both preset and custom colors.
        """
        class TestModel(FilamentConfigMixin):
            pass

        with pytest.raises(ValueError, match="Cannot provide both"):
            TestModel(
                filamentPreset=FilamentPreset.BAMBU_CMYW,
                filamentColors=[
                    FilamentColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
                    FilamentColorConfig(name='Green', hex='#00FF00', transmission_distance=3.0),
                    FilamentColorConfig(name='Blue', hex='#0000FF', transmission_distance=3.0),
                    FilamentColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=3.0),
                ]
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
