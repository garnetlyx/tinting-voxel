"""
QA Round 10 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.

Note: QA-93, QA-94, QA-97, QA-99, QA-101, QA-105, QA-106 were found during
this round but are already fixed in uncommitted changes. Only unfixed bugs
have failing tests below.
"""
import inspect

import numpy as np
import pytest

from core.blend_color import Color, Colors, BlendTestGenerator, _code_to_rgb_cached, clear_rgb_cache
from core.color_config import ColorConfig


# -- QA-95: threemf_generator imports unused symbols ---------------------------
# File: backend/services/threemf_generator.py:16
# The import line `from core.blend_color import BlendTestGenerator, Color, Colors`
# imports BlendTestGenerator and Color, but only Colors is used in the module.
# BlendTestGenerator and Color are unused imports that add unnecessary coupling.

class TestQA95ThreeMFUnusedImports:
    """threemf_generator.py imports BlendTestGenerator and Color but doesn't use them."""

    def test_threemf_no_unused_blend_imports(self):
        """threemf_generator should not import unused BlendTestGenerator."""
        from services import threemf_generator

        source = inspect.getsource(threemf_generator)

        # Check if BlendTestGenerator appears in any import line
        lines = source.split('\n')
        import_lines = [
            line for line in lines
            if 'BlendTestGenerator' in line and 'import' in line
        ]

        assert len(import_lines) == 0, (
            "BUG QA-95: threemf_generator.py imports BlendTestGenerator "
            "from core.blend_color but never uses it. This is a dead import "
            "that adds unnecessary coupling between the service and the "
            "test generator class."
        )


# -- QA-96: compute_reference_matrices pads matrix with empty-string codes ------
# File: backend/services/stl_generator.py:75-79
# When the number of permutations (n) is not a perfect rectangle (rows*cols),
# the code pads with empty strings '' and (255,255,255) white.
# These padding entries end up in the DataFrame and are considered during
# map_to_nearest_color lookups. An input color that is closest to white
# could match the padding entry instead of a real blend code, returning
# an empty string '' as the blend_code. This would then fail when iterating
# `for z_idx, code_char in enumerate(blend_code)` with zero iterations
# (empty string = no layers generated for that color block).

class TestQA96PaddedEmptyCodesInReferenceMatrix:
    """compute_reference_matrices includes empty-string padding codes that
    can match as nearest color in map_to_nearest_color."""

    def test_reference_matrix_contains_no_empty_codes(self):
        """Reference code matrix should not contain empty string entries.

        Uses 5 colors with 1 layer = 5 combos. sqrt(5)≈2.23, int=2, cols=3.
        rows*cols = 6 > 5, so 1 padded entry with empty string code is added.
        """
        from services.stl_generator import compute_reference_matrices

        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
        ]
        colors = Colors.from_configs(configs)
        code_df, rgb_df = compute_reference_matrices(1, 0.08, colors)

        empty_count = 0
        for r in range(code_df.shape[0]):
            for c in range(code_df.shape[1]):
                val = code_df.iat[r, c]
                if val == '' or val is None or (isinstance(val, str) and val.strip() == ''):
                    empty_count += 1

        assert empty_count == 0, (
            f"BUG QA-96: compute_reference_matrices pads reference matrix "
            f"with {empty_count} empty-string entries. These can match as "
            f"'nearest color' for white/light inputs in map_to_nearest_color, "
            f"returning empty blend codes that produce zero layers."
        )

    def test_white_input_does_not_match_empty_code(self):
        """A white input color should match a real blend code, not empty padding."""
        from services.stl_generator import compute_reference_matrices

        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
        ]
        colors = Colors.from_configs(configs)
        code_df, rgb_df = compute_reference_matrices(1, 0.08, colors)

        # White input should match 'W' (white filament), not empty padding
        input_colors = [(255, 255, 255)]
        result_codes, _ = Color.map_to_nearest_color(input_colors, code_df, rgb_df)

        assert result_codes[0] != '', (
            f"BUG QA-96: White input (255,255,255) matched empty padding code "
            f"instead of a real blend code. The padding entry's white RGB "
            f"(255,255,255) is closer to the input than any blended color, "
            f"causing zero layers to be generated."
        )


# -- QA-98: map_to_nearest_color returns scaled ref_colors, not original RGB ----
# File: backend/core/blend_color.py:140,156
# At line 140: ref_colors = np.array(ref_colors) / 255.0
# This normalizes ref_colors IN PLACE (overwrites the list contents).
# At line 156: results_color.append(ref_colors[nearest_idx]*255)
# This multiplies back, but due to floating point precision, the RGB values
# are not exact integers. For example, 128 -> 128/255 = 0.50196... -> *255 = 128.0
# which is fine, but 1 -> 1/255 = 0.00392... -> *255 = 0.99999... (not exactly 1).
# The returned RGB values have floating point error instead of being exact ints.

class TestQA98MapToNearestColorPrecision:
    """map_to_nearest_color returns floating-point RGB instead of integer."""

    def test_returned_rgb_values_are_exact_integers(self):
        """map_to_nearest_color should return integer RGB values, not floats with precision errors."""
        from services.stl_generator import compute_reference_matrices

        colors = Colors()
        code_df, rgb_df = compute_reference_matrices(4, 0.08, colors)

        # Use a known exact color from the reference matrix
        first_rgb = rgb_df.iat[0, 0]
        input_colors = [first_rgb]

        _, result_rgbs = Color.map_to_nearest_color(input_colors, code_df, rgb_df)

        # The returned RGB should be exact (no floating point drift)
        result_rgb = result_rgbs[0]
        for i, channel in enumerate(['R', 'G', 'B']):
            val = result_rgb[i]
            # Check if value is exactly an integer (no floating point drift)
            assert val == round(val), (
                f"BUG QA-98: map_to_nearest_color returns float RGB values with "
                f"precision errors. {channel}={val} (expected integer). "
                f"ref_colors is normalized to [0,1] at line 140, then multiplied "
                f"back at line 156, introducing floating-point drift."
            )
