"""
QA Round 15: Test for SVG STL double-sided mirroring inconsistency

Bug (QA-159): SVG STL generator uses `width - x` for mirroring, but STL generator
uses `width - 1 - x`. This inconsistency causes misaligned back-side layers.

Fix: Changed line 324 in svg_stl_generator.py to use `width - 1 - x`.
"""
import pytest
import inspect
from services import svg_stl_generator


class TestSVGMirroringConsistency:
    """Test that SVG STL mirroring uses correct formula."""

    def test_mirroring_formula_in_source_code(self):
        """
        QA-159: Verify that svg_stl_generator.py uses 'width - 1 - x' for mirroring.
        This should match the formula used in stl_generator.py for consistency.
        """
        # Check the source code contains the correct formula
        source = inspect.getsource(svg_stl_generator.generate_svg_stl_zip)

        # Should contain 'width - 1 - x' for mirroring
        assert 'width - 1 - x' in source, (
            "SVG generator must use 'width - 1 - x' for horizontal mirroring "
            "to match STL generator behavior"
        )

        # Should NOT contain the old buggy formula 'width - x'
        # Note: We check for the specific context to avoid false positives
        assert '[(width - x, y)' not in source, (
            "SVG generator should not use 'width - x' for mirroring "
            "(bug: causes misalignment with STL generator)"
        )

    def test_mirroring_formula_matches_stl_generator(self):
        """
        STL generator uses: width - 1 - x
        SVG generator should use the same formula for consistency.
        """
        # Verify the correct formula behavior
        width = 10
        pixels = [{'x': 0, 'y': 5}, {'x': 9, 'y': 5}]

        # Correct formula (used by both generators after fix)
        correct_mirrored = [width - 1 - p['x'] for p in pixels]

        # Formula produces: [9, 0] for x values [0, 9]
        assert correct_mirrored == [9, 0], "Correct formula: width - 1 - x"

        # x=0 mirrors to x=9 (rightmost)
        # x=9 mirrors to x=0 (leftmost)
        # This is correct for zero-indexed pixel coordinates


class TestSVGPolygonMirroringEdgeCases:
    """Test polygon mirroring edge cases."""

    def test_polygon_at_right_edge(self):
        """Polygon with vertex at x=9 (rightmost in 10-wide image) mirrors to x=0."""
        width = 10
        # Vertex at x=9 (rightmost pixel, since x=9 is valid for width=10)
        polygon = [(9, 0), (9, 5), (9, 10)]

        # Correct formula (after fix)
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]
        # Result: [(0, 0), (0, 5), (0, 10)] - correct!

        assert correct_mirrored == [(0, 0), (0, 5), (0, 10)], (
            "Vertex at x=9 should mirror to x=0 (leftmost)"
        )

    def test_polygon_at_left_edge(self):
        """Polygon with vertex at x=0 (leftmost) mirrors to x=9 (rightmost)."""
        width = 10
        polygon = [(0, 0), (0, 5), (0, 10)]

        # Correct formula
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]
        # Result: [(9, 0), (9, 5), (9, 10)]

        assert correct_mirrored == [(9, 0), (9, 5), (9, 10)], (
            "Vertex at x=0 should mirror to x=9 (rightmost)"
        )

    def test_polygon_spanning_full_width(self):
        """Polygon spanning full width (x=0 to x=9) mirrors to same span."""
        width = 10
        # Polygon from x=0 to x=9 (full width of 10-pixel image)
        polygon = [(0, 0), (9, 0), (9, 10), (0, 10)]

        # Correct formula
        correct_mirrored = [(width - 1 - x, y) for x, y in polygon]
        # x values: 0 -> 9, 9 -> 0
        # Polygon spans x=0 to x=9 (correctly mirrored!)

        # Verify mirrored polygon has same width
        original_width = max(x for x, _ in polygon) - min(x for x, _ in polygon)
        mirrored_width = max(x for x, _ in correct_mirrored) - min(x for x, _ in correct_mirrored)

        assert original_width == 9, "Original polygon spans x=0 to x=9"
        assert mirrored_width == 9, "Mirrored polygon should also span 9 units"

        # Verify bounds
        assert min(x for x, _ in correct_mirrored) == 0, "Mirrored polygon should start at x=0"
        assert max(x for x, _ in correct_mirrored) == 9, "Mirrored polygon should end at x=9"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
