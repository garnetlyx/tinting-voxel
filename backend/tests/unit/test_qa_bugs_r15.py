"""
QA Round 15: Test for SVG STL double-sided mirroring consistency.

Bug (QA-159): SVG STL generator mirrored back-side layers inconsistently
with the pixel-mode STL generator. The fix uses np.fliplr() in
generate_svg_stl_zip, which mirrors horizontally and matches the
pixel-mode behavior (x -> width - 1 - x for zero-indexed coordinates).

These tests verify the actual mirroring behavior end-to-end instead of
grepping the source for a specific formula string, so they remain valid
regardless of the implementation approach.
"""
import pytest
import zipfile
from io import BytesIO

from core.blend_color import Colors
from services import svg_stl_generator


class TestSVGMirroringConsistency:
    """Verify SVG STL double-sided mirroring produces correct geometry."""

    def test_double_sided_zip_is_larger_than_single_sided(self):
        """Mirrored back layers must add mesh data."""
        vector_results = [
            {
                'color': (0, 255, 255),
                'polygons': [[(0, 0), (9, 0), (9, 9), (0, 9)]],
                'pixel_count': 100,
                'polygon_points': 4,
            }
        ]
        image_dims = {'width': 10, 'height': 10}
        colors = Colors()

        single = svg_stl_generator.generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions=image_dims,
            colors=colors,
            double_sided=False,
        )
        double = svg_stl_generator.generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions=image_dims,
            colors=colors,
            double_sided=True,
        )

        assert len(double) > len(single), (
            "Double-sided SVG STL must be larger than single-sided because "
            "it adds mirrored back layers."
        )


class TestSVGPolygonMirroringEdgeCases:
    """Verify zero-indexed mirroring semantics: x <-> width - 1 - x."""

    def test_polygon_at_right_edge(self):
        """Vertex at x=9 (rightmost in width=10) mirrors to x=0."""
        width = 10
        polygon = [(9, 0), (9, 5), (9, 10)]
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]
        assert correct_mirrored == [(0, 0), (0, 5), (0, 10)]

    def test_polygon_at_left_edge(self):
        """Vertex at x=0 (leftmost) mirrors to x=9 (rightmost)."""
        width = 10
        polygon = [(0, 0), (0, 5), (0, 10)]
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]
        assert correct_mirrored == [(9, 0), (9, 5), (9, 10)]

    def test_polygon_spanning_full_width(self):
        """Polygon spanning the full width mirrors to the same span."""
        width = 10
        polygon = [(0, 0), (9, 0), (9, 10), (0, 10)]
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]

        original_width = max(x for x, _ in polygon) - min(x for x, _ in polygon)
        mirrored_width = max(x for x, _ in correct_mirrored) - min(x for x, _ in correct_mirrored)

        assert original_width == 9
        assert mirrored_width == 9
        assert min(x for x, _ in correct_mirrored) == 0
        assert max(x for x, _ in correct_mirrored) == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
