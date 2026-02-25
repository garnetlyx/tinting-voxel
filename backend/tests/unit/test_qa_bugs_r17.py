"""
QA Round 17: Tests for edge cases and potential bugs found in R17

This test file covers:
1. Colors.from_configs accepts fewer than 4 colors (should enforce min 4)
2. Frontend/Backend validation consistency
"""
import pytest

from api.models import FilamentColorConfig
from core.blend_color import Colors
from core.color_config import ColorConfig


class TestColorsMinValidation:
    """Test Colors.from_configs enforces minimum 4 colors."""

    def test_colors_from_configs_rejects_three_colors(self):
        """
        QA-172: Colors.from_configs accepts 3 colors without validation error.

        Expected: Should enforce minimum 4 colors (same as FilamentConfigMixin).
        Actual: Accepts 3 colors silently.
        """
        # This should fail but currently passes
        with pytest.raises(ValueError, match="at least 4 colors"):
            Colors.from_configs([
                ColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
                ColorConfig(name='Green', hex='#00FF00', transmission_distance=3.0),
                ColorConfig(name='Blue', hex='#0000FF', transmission_distance=3.0),
            ])

    def test_colors_from_configs_accepts_four_colors(self):
        """Verify 4 colors work correctly."""
        colors = Colors.from_configs([
            ColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
            ColorConfig(name='Green', hex='#00FF00', transmission_distance=3.0),
            ColorConfig(name='Blue', hex='#0000FF', transmission_distance=3.0),
            ColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=2.5),
        ])
        assert len(colors) == 4

    def test_colors_from_configs_rejects_two_colors(self):
        """Verify 2 colors are rejected."""
        with pytest.raises(ValueError, match="at least 4 colors"):
            Colors.from_configs([
                ColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
                ColorConfig(name='Green', hex='#00FF00', transmission_distance=3.0),
            ])

    def test_colors_from_configs_rejects_one_color(self):
        """Verify 1 color is rejected."""
        with pytest.raises(ValueError, match="at least 4 colors"):
            Colors.from_configs([
                ColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
            ])

    def test_colors_from_configs_rejects_empty_list(self):
        """Verify empty list is rejected."""
        with pytest.raises(ValueError, match="at least 4 colors"):
            Colors.from_configs([])


class TestFrontendBackendValidationConsistency:
    """Test that frontend and backend validation are consistent."""

    def test_backend_rejects_3_filament_colors(self):
        """Backend FilamentConfigMixin enforces min 4 via min_length."""
        from api.models import DownloadSTLRequestV2, ImageDimensions

        with pytest.raises(Exception) as exc_info:  # ValidationError
            DownloadSTLRequestV2(
                filamentColors=[
                    FilamentColorConfig(name='Red', hex='#FF0000', transmission_distance=3.0),
                    FilamentColorConfig(name='Green', hex='#00FF00', transmission_distance=3.0),
                    FilamentColorConfig(name='Blue', hex='#0000FF', transmission_distance=3.0),
                ],
                colorBlocks=[{'r': 255, 'g': 0, 'b': 0, 'pixels': [{'x': 0, 'y': 0}]}],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions=ImageDimensions(width=100, height=100)
            )

        # Should fail with "too_short" error for filamentColors
        assert "too_short" in str(exc_info.value) or "at least 4" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
