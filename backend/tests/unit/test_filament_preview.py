"""
Unit tests for the FilamentPreviewService.
"""
import base64

import pytest

from core.blend_color import Colors
from core.color_config import BAMBU_CMYK_PRESET, CLEAR_CMYK_PRESET, ColorConfig
from services.filament_preview import FilamentPreviewService


class TestFilamentPreviewService:
    """Tests for FilamentPreviewService."""

    def test_generate_preview_returns_base64_png(self):
        """Preview returns a base64-encoded PNG image."""
        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert "image" in result
        # Should be valid base64
        decoded = base64.b64decode(result["image"])
        # PNG magic bytes
        assert decoded[:4] == b'\x89PNG'

    def test_generate_preview_returns_color_matrix(self):
        """Preview returns a color matrix with codes and RGB values."""
        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert "colorMatrix" in result
        matrix = result["colorMatrix"]
        assert len(matrix) > 0
        # Each entry should have code and rgb
        first = matrix[0]
        assert "code" in first
        assert "rgb" in first
        assert len(first["rgb"]) == 3

    def test_generate_preview_returns_stats(self):
        """Preview returns stats about the color configuration."""
        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert "stats" in result
        stats = result["stats"]
        assert "colorCount" in stats
        assert "combinationCount" in stats
        assert stats["colorCount"] == 4

    def test_generate_preview_with_custom_colors(self):
        """Preview works with custom color configurations."""
        configs = [
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=3.0),
            ColorConfig(name="Blue", hex="#0000FF", transmission_distance=1.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.0),
        ]
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert result["stats"]["colorCount"] == 4
        # 4 colors, 4 layers = 4^4 = 256 combinations
        assert result["stats"]["combinationCount"] == 256

    def test_generate_preview_with_bambu_preset(self):
        """Preview works with Bambu CMYK preset."""
        colors = Colors.from_configs(BAMBU_CMYK_PRESET)
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert result["stats"]["colorCount"] == 4

    def test_generate_preview_with_clear_preset(self):
        """Preview works with Clear CMYK preset."""
        colors = Colors.from_configs(CLEAR_CMYK_PRESET)
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert result["stats"]["colorCount"] == 4

    def test_generate_preview_with_6_colors(self):
        """Preview works with 6 color configurations."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Black", hex="#000000", transmission_distance=0.5),
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
        ]
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert result["stats"]["colorCount"] == 6
        # 6 colors, 4 layers = 6^4 = 1296 combinations
        assert result["stats"]["combinationCount"] == 1296

    def test_generate_preview_with_16_colors_paginated(self):
        """Preview works with 16 color configurations using pagination."""
        configs = [
            ColorConfig(name="Aqua", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Berry", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Citrus", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="Dove", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Ebony", hex="#000000", transmission_distance=0.5),
            ColorConfig(name="Flame", hex="#FF4500", transmission_distance=2.0),
            ColorConfig(name="Grass", hex="#00FF00", transmission_distance=3.5),
            ColorConfig(name="Harbor", hex="#0000FF", transmission_distance=1.5),
            ColorConfig(name="Ivory", hex="#FFFFF0", transmission_distance=6.0),
            ColorConfig(name="Jade", hex="#00A86B", transmission_distance=2.8),
            ColorConfig(name="Khaki", hex="#C3B091", transmission_distance=4.0),
            ColorConfig(name="Lemon", hex="#FFF44F", transmission_distance=3.2),
            ColorConfig(name="Mint", hex="#98FF98", transmission_distance=5.0),
            ColorConfig(name="Navy", hex="#000080", transmission_distance=1.0),
            ColorConfig(name="Olive", hex="#808000", transmission_distance=2.2),
            ColorConfig(name="Plum", hex="#8E4585", transmission_distance=1.7),
        ]
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=2, layer_height=0.08)
        result = service.generate_preview(page=1, page_size=100)
        assert result["stats"]["colorCount"] == 16
        # 16 colors, 2 layers = 16^2 = 256 total
        assert result["stats"]["combinationCount"] == 256
        assert result["pagination"]["totalCombinations"] == 256
        assert len(result["colorMatrix"]) == 100

    def test_generate_preview_image_dimensions(self):
        """Preview image has reasonable dimensions."""
        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        result = service.generate_preview()
        assert "imageDimensions" in result
        dims = result["imageDimensions"]
        assert "width" in dims
        assert "height" in dims
        assert dims["width"] > 0
        assert dims["height"] > 0

    def test_check_similar_colors(self):
        """Similar colors detection identifies near-duplicate filament colors."""
        # Use colors with different first letters but very similar hex values
        # LAB distance between #00FFFF and #00E0FF is ~21
        configs = [
            ColorConfig(name="Aqua", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Baby blue", hex="#00E0FF", transmission_distance=3.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
        ]
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        warnings = service.check_similar_colors(threshold=25.0)
        assert len(warnings) > 0
        # Should flag Aqua and Baby blue as similar
        assert any("Aqua" in w and "Baby blue" in w for w in warnings)

    def test_check_similar_colors_no_warnings(self):
        """No warnings when colors are sufficiently different."""
        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)
        warnings = service.check_similar_colors(threshold=10.0)
        assert len(warnings) == 0


class TestFilamentPreviewPagination:
    """Tests for paginated preview generation."""

    @pytest.fixture
    def service(self):
        colors = Colors()
        return FilamentPreviewService(colors, layer_count=4, layer_height=0.08)

    def test_paginated_returns_page_info(self, service):
        """Paginated preview includes pagination metadata."""
        result = service.generate_preview(page=1, page_size=50)
        assert "pagination" in result
        p = result["pagination"]
        assert p["page"] == 1
        assert p["pageSize"] == 50
        assert p["totalCombinations"] == 256
        assert p["totalPages"] == 6  # ceil(256 / 50)

    def test_paginated_limits_color_matrix(self, service):
        """Color matrix length matches page_size for non-last pages."""
        result = service.generate_preview(page=1, page_size=50)
        assert len(result["colorMatrix"]) == 50

    def test_paginated_last_page_remainder(self, service):
        """Last page returns remaining items."""
        result = service.generate_preview(page=6, page_size=50)
        # 256 total, pages 1-5 have 50 each = 250, page 6 has 6
        assert len(result["colorMatrix"]) == 6

    def test_paginated_image_matches_page(self, service):
        """Paginated preview image covers only the current page's entries."""
        result = service.generate_preview(page=1, page_size=50)
        # Image should be rendered for 50 items, not 256
        dims = result["imageDimensions"]
        assert dims["width"] > 0
        assert dims["height"] > 0
        # For 50 items: ceil(sqrt(50))=8 cols, ceil(50/8)=7 rows
        cell_size = 12
        expected_cols = 8
        expected_rows = 7
        assert dims["width"] == expected_cols * cell_size
        assert dims["height"] == expected_rows * cell_size

    def test_unpaginated_returns_all(self, service):
        """Without pagination params, returns all combinations."""
        result = service.generate_preview()
        assert len(result["colorMatrix"]) == 256
        assert "pagination" not in result

    def test_paginated_page_out_of_range(self, service):
        """Page beyond totalPages raises ValueError."""
        import pytest
        with pytest.raises(ValueError, match="out of range"):
            service.generate_preview(page=100, page_size=50)

    def test_paginated_stats_always_total(self, service):
        """Stats always reflect total combination count regardless of page."""
        result = service.generate_preview(page=2, page_size=50)
        assert result["stats"]["combinationCount"] == 256
