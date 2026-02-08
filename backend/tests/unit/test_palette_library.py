"""
Unit tests for the palette library.
"""
import pytest

from core.palette_library import (
    ALL_PALETTES,
    CATEGORIES,
    get_all_categories,
    get_palette,
    get_palettes_by_category,
)


class TestPaletteLibrary:
    """Tests for palette library data and query functions."""

    def test_all_palettes_not_empty(self):
        """Library has at least one palette."""
        assert len(ALL_PALETTES) > 0

    def test_all_palettes_have_unique_ids(self):
        """All palette IDs are unique."""
        ids = [p.id for p in ALL_PALETTES]
        assert len(ids) == len(set(ids))

    def test_all_palettes_have_at_least_4_colors(self):
        """Each palette has at least 4 colors (minimum for printing)."""
        for p in ALL_PALETTES:
            assert len(p.colors) >= 4, f"Palette '{p.id}' has only {len(p.colors)} colors"

    def test_all_palettes_have_unique_first_letters(self):
        """Each palette's colors have unique first letters (required by Colors)."""
        for p in ALL_PALETTES:
            labels = [c.name[0].upper() for c in p.colors]
            assert len(labels) == len(set(labels)), (
                f"Palette '{p.id}' has duplicate first letters: {labels}"
            )

    def test_all_palettes_have_valid_hex(self):
        """All color hex values are valid #RRGGBB format."""
        import re
        for p in ALL_PALETTES:
            for c in p.colors:
                assert re.match(r'^#[0-9a-fA-F]{6}$', c.hex), (
                    f"Palette '{p.id}', color '{c.name}' has invalid hex: {c.hex}"
                )

    def test_all_palettes_have_positive_td(self):
        """All transmission distances are positive."""
        for p in ALL_PALETTES:
            for c in p.colors:
                assert c.transmission_distance > 0, (
                    f"Palette '{p.id}', color '{c.name}' has td={c.transmission_distance}"
                )

    def test_all_palettes_have_valid_category(self):
        """All palettes belong to a known category."""
        for p in ALL_PALETTES:
            assert p.category in CATEGORIES, (
                f"Palette '{p.id}' has unknown category: {p.category}"
            )

    def test_get_palette_found(self):
        """Get an existing palette by ID."""
        palette = get_palette("bambu_cmyk")
        assert palette is not None
        assert palette.id == "bambu_cmyk"
        assert palette.name == "Bambu CMYK"

    def test_get_palette_not_found(self):
        """Get a non-existent palette returns None."""
        assert get_palette("nonexistent") is None

    def test_get_palettes_by_category(self):
        """Filter palettes by category."""
        standard = get_palettes_by_category("standard")
        assert len(standard) >= 2
        assert all(p.category == "standard" for p in standard)

    def test_get_palettes_by_category_empty(self):
        """Unknown category returns empty list."""
        assert get_palettes_by_category("unknown") == []

    def test_get_all_categories(self):
        """Get all category names."""
        cats = get_all_categories()
        assert "standard" in cats
        assert "artistic" in cats
        assert "specialty" in cats

    def test_categories_descriptions(self):
        """Category descriptions are non-empty strings."""
        for cat, desc in CATEGORIES.items():
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_palette_colors_are_valid_color_configs(self):
        """Palette colors can be used with Colors.from_configs."""
        from core.blend_color import Colors

        for p in ALL_PALETTES:
            colors = Colors.from_configs(p.colors)
            assert len(colors) == len(p.colors)
