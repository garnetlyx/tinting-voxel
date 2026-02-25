"""
QA Round 18: Tests for edge cases and potential bugs found in R18

This test file covers:
1. BlendTestGenerator.generate_box missing validation (inconsistent with stl_generator)
2. permutation_matrix accepts count=0 without validation
"""
import pytest
import numpy as np

from core.blend_color import BlendTestGenerator


class TestBlendTestGeneratorValidation:
    """Test BlendTestGenerator has same validation as stl_generator.generate_box."""

    def test_generate_box_rejects_negative_x(self):
        """
        QA-174: BlendTestGenerator.generate_box accepts negative coordinates.

        Expected: Should reject negative coordinates (same as stl_generator.generate_box).
        Actual: Accepts negative coordinates silently.
        """
        gen = BlendTestGenerator()

        # stl_generator.generate_box raises ValueError for negative coords
        with pytest.raises(ValueError, match="non-negative"):
            gen.generate_box((-1, 1), (0, 1), (0, 1))

    def test_generate_box_rejects_negative_y(self):
        """Verify negative y coordinates are rejected."""
        gen = BlendTestGenerator()

        with pytest.raises(ValueError, match="non-negative"):
            gen.generate_box((0, 1), (-1, 1), (0, 1))

    def test_generate_box_rejects_negative_z(self):
        """Verify negative z coordinates are rejected."""
        gen = BlendTestGenerator()

        with pytest.raises(ValueError, match="non-negative"):
            gen.generate_box((0, 1), (0, 1), (-1, 1))

    def test_generate_box_rejects_inverted_x_range(self):
        """
        QA-175: BlendTestGenerator.generate_box accepts inverted ranges.

        Expected: Should reject inverted ranges (same as stl_generator.generate_box).
        Actual: Accepts inverted ranges silently.
        """
        gen = BlendTestGenerator()

        # stl_generator.generate_box raises ValueError for inverted ranges
        with pytest.raises(ValueError, match="start must be less than end"):
            gen.generate_box((1, 0), (0, 1), (0, 1))

    def test_generate_box_rejects_inverted_y_range(self):
        """Verify inverted y range is rejected."""
        gen = BlendTestGenerator()

        with pytest.raises(ValueError, match="start must be less than end"):
            gen.generate_box((0, 1), (1, 0), (0, 1))

    def test_generate_box_rejects_inverted_z_range(self):
        """Verify inverted z range is rejected."""
        gen = BlendTestGenerator()

        with pytest.raises(ValueError, match="start must be less than end"):
            gen.generate_box((0, 1), (0, 1), (1, 0))

    def test_generate_box_accepts_valid_coordinates(self):
        """Verify valid coordinates work correctly."""
        gen = BlendTestGenerator()

        result = gen.generate_box((0, 1), (0, 1), (0, 1))
        assert result is not None
        # Returns stl.mesh.Mesh object with points attribute
        assert hasattr(result, 'points')


class TestPermutationMatrixValidation:
    """Test permutation_matrix validates count parameter."""

    def test_permutation_matrix_rejects_zero_count(self):
        """
        QA-176: permutation_matrix accepts count=0 and returns empty DataFrame.

        Expected: Should reject count=0 (invalid parameter).
        Actual: Returns empty DataFrame which can cause downstream issues.
        """
        gen = BlendTestGenerator()

        # count=0 should raise an error, not return empty DataFrame
        with pytest.raises(ValueError, match="positive|cannot be zero|must be positive"):
            gen.permutation_matrix(['A', 'B', 'C'], 0)

    def test_permutation_matrix_accepts_positive_count(self):
        """Verify positive count works correctly."""
        gen = BlendTestGenerator()

        result = gen.permutation_matrix(['A', 'B', 'C'], 2)
        assert result.shape == (3, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
