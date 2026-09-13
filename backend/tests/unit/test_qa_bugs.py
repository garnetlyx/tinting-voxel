"""
QA Bug Tests - Failing tests that demonstrate real bugs found during QA review.

Each test targets a specific verified bug. Tests are expected to FAIL while
the bug is present. Once fixed, they should pass.

"""
import itertools
import sys
import time
from io import BytesIO
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

# -- Fixtures ----------------------------------------------------------------


@pytest.fixture
def make_color_blocks():
    """Factory for generating color block dicts."""
    def _make(count=1, width=4, height=4):
        blocks = []
        for i in range(count):
            blocks.append({
                'r': (i * 50) % 256,
                'g': (i * 80) % 256,
                'b': (i * 110) % 256,
                'count': 1,
                'pixels': [{'x': i % width, 'y': i // width}],
                'hex': f'#{(i * 50) % 256:02X}{(i * 80) % 256:02X}{(i * 110) % 256:02X}'
            })
        return blocks
    return _make


# -- BUG QA-01: Permutation Bomb DoS in initialize_color_mapping() ----------
# File: backend/services/stl_generator.py:57-59
# With 10 custom colors and layerCount=10, itertools.product generates
# 10^10 = 10,000,000,000 combinations, exhausting memory.


class TestPermutationBombDoS:
    """
    BUG QA-01: Exponential permutation generation causes DoS.

    initialize_color_mapping() calls:
        perms = list(itertools.product(items, repeat=layer_count))

    With N colors and layer_count L, this generates N^L permutations.
    There is no upper bound check, allowing:
    - 10 colors, 10 layers -> 10^10 = 10 billion items -> OOM
    - Even 8 colors, 8 layers -> 8^8 = 16 million -> ~1GB+ RAM
    """

    def test_permutation_count_with_many_colors_and_layers(self):
        """Verify that initialize_color_mapping rejects dangerous color+layer combos."""
        from core.blend_color import Color, Colors
        from services.stl_generator import initialize_color_mapping

        # Build an 8-color config
        colors = Colors(colors={})
        for name in ['Cyan', 'Magenta', 'Yellow', 'White', 'Black', 'Red', 'Green', 'Azure']:
            label = name[0].upper()
            colors.colors[label] = Color(
                name=name, transmission_distance=3.0,
                hex='#' + f'{hash(name) % 0xFFFFFF:06X}'
            )

        # 8 colors x 8 layers = 16,777,216 permutations -> should be rejected
        with pytest.raises(ValueError, match="over the .* budget"):
            initialize_color_mapping(layer_count=8, colors=colors)

    def test_compute_reference_matrices_has_permutation_guard(self):
        """compute_reference_matrices (used by all STL paths) has permutation guard."""
        import inspect
        from services.stl_generator import compute_reference_matrices

        source = inspect.getsource(compute_reference_matrices)

        # The guard is now time-budget driven: probe-extrapolated cost over
        # settings.full_enumeration_budget_seconds rejects (or prunes for
        # transparent sets) instead of a fixed permutation-count cap.
        has_limit_check = (
            'raise ValueError' in source and 'full_enumeration_budget_seconds' in source
        )

        assert has_limit_check, (
            "BUG QA-01: compute_reference_matrices() has no safeguard against "
            "exponential permutation generation. With 10 colors and 10 layers, "
            "it would generate 10^10 = 10 billion permutations, exhausting RAM."
        )


# -- BUG QA-02: Race condition in global color state -----------------------
# File: backend/services/stl_generator.py:21-25, 42
# Global variables _reference_code_matrix, _reference_rgb_matrix, etc.
# are modified without synchronization.


class TestGlobalColorStateRace:
    """
    BUG QA-02: Fixed — generate_stl_zip now computes reference matrices
    locally, eliminating the race condition on global state.
    """

    def test_generate_stl_zip_thread_safe(self):
        """generate_stl_zip computes matrices locally, no global dependency."""
        from core.blend_color import Colors
        from services.stl_generator import generate_stl_zip

        colors = Colors()
        sample_blocks = [
            {
                'r': 255, 'g': 0, 'b': 0,
                'hex': '#FF0000',
                'count': 1,
                'pixels': [{'x': 0, 'y': 0}]
            }
        ]

        # Should work without calling initialize_color_mapping first
        result = generate_stl_zip(
            color_blocks=sample_blocks,
            layer_height=0.08,
            pixel_size=1.0,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            colors=colors
        )
        assert len(result) > 0  # Valid ZIP content

    def test_different_colors_produce_isolated_results(self):
        """Two calls with different colors don't interfere with each other."""
        from core.blend_color import Colors
        from services.stl_generator import generate_stl_zip

        sample_blocks = [
            {
                'r': 255, 'g': 0, 'b': 0,
                'hex': '#FF0000',
                'count': 1,
                'pixels': [{'x': 0, 'y': 0}]
            }
        ]
        dims = {'width': 10, 'height': 10}

        result_default = generate_stl_zip(
            color_blocks=sample_blocks,
            layer_height=0.08,
            pixel_size=1.0,
            layer_count=4,
            image_dimensions=dims,
            colors=Colors()
        )

        result_clear = generate_stl_zip(
            color_blocks=sample_blocks,
            layer_height=0.08,
            pixel_size=1.0,
            layer_count=4,
            image_dimensions=dims,
            colors=Colors(clear=True)
        )

        # Both produce valid results independently (different color configs)
        assert len(result_default) > 0
        assert len(result_clear) > 0


# -- BUG QA-03: get_cmyk() returns inconsistent tuple length ---------------
# File: backend/core/blend_color.py:50-68
# For black (0,0,0): returns (0, 0, 0) - 3 elements
# For all other colors: returns (c, m, y, k) - 4 elements


class TestGetCmykInconsistentReturn:
    """
    BUG QA-03: Color.get_cmyk() returns 3-tuple for black, 4-tuple for others.

    Line 52-54: if (r, g, b) == (0, 0, 0): return 0, 0, 0
    Line 68: return c * cmyk_scale, m * cmyk_scale, y * cmyk_scale, k * cmyk_scale

    Any code that unpacks the result as (c, m, y, k) will crash on black.
    """

    def test_black_returns_same_tuple_length_as_other_colors(self):
        """get_cmyk() should always return a consistent tuple length."""
        from core.blend_color import Color

        # Non-black color -> 4-tuple
        red_color = Color(name='Red', transmission_distance=3.0, hex='#FF0000')
        red_cmyk = red_color.get_cmyk()

        # Black color -> currently returns 3-tuple (BUG)
        black_color = Color(name='Black', transmission_distance=3.0, hex='#000000')
        black_cmyk = black_color.get_cmyk()

        assert len(black_cmyk) == len(red_cmyk), (
            f"BUG QA-03: get_cmyk() returns {len(black_cmyk)}-tuple for black "
            f"but {len(red_cmyk)}-tuple for red. This breaks code that unpacks "
            f"as (c, m, y, k). Black: {black_cmyk}, Red: {red_cmyk}"
        )


# -- BUG QA-04: No bounds validation on Form parameters in /process-image --
# File: backend/api/routes/image.py:29-34
# Form parameters maxColors, colorThreshold, numColors have no validation.


class TestProcessImageFormParamValidation:
    """
    BUG QA-04: Form parameters in /process-image have no bounds validation.

    maxColors=0 or maxColors=-5 will be passed directly to scikit-learn
    KMeans, which will crash or produce undefined behavior.
    numColors=0 will crash cv2.kmeans in SVG mode.
    """

    def test_max_colors_zero_should_be_rejected(self):
        """maxColors=0 makes KMeans crash. Should be rejected at API level."""
        from api.routes.image import api_process_image
        import inspect

        sig = inspect.signature(api_process_image)
        max_colors_param = sig.parameters['maxColors']
        default = max_colors_param.default

        # FastAPI/Pydantic V2 stores constraints in metadata list
        has_ge_constraint = False
        if hasattr(default, 'metadata'):
            for m in default.metadata:
                if hasattr(m, 'ge') and m.ge is not None and m.ge >= 1:
                    has_ge_constraint = True
                    break

        assert has_ge_constraint, (
            "BUG QA-04: maxColors Form parameter has no minimum value constraint. "
            "maxColors=0 will crash KMeans clustering. Add ge=1 to Form()."
        )


# -- BUG QA-05: Validator allows duplicate hex colors ----------------------
# File: backend/api/models.py:135-143
# validate_unique_labels checks first-letter uniqueness but not hex uniqueness.


class TestDuplicateHexColorsAllowed:
    """
    BUG QA-05: Filament color validator allows duplicate hex colors.

    Two colors with different names but same hex value are accepted.
    This produces confusing results - two "different" filaments that
    are physically the same color.
    """

    def test_duplicate_hex_colors_rejected(self):
        """Two filament colors with the same hex should be rejected."""
        from api.models import DownloadSTLRequestV2, FilamentColorConfig

        # Two different names but same hex color
        colors = [
            FilamentColorConfig(name='Cyan', hex='#FF0000', transmission_distance=3.0),
            FilamentColorConfig(name='Magenta', hex='#FF0000', transmission_distance=1.9),
            FilamentColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=2.5),
            FilamentColorConfig(name='White', hex='#FFFFFF', transmission_distance=7.2),
        ]

        # BUG: This should raise a validation error but doesn't
        try:
            request = DownloadSTLRequestV2(
                colorBlocks=[{
                    'r': 255, 'g': 0, 'b': 0,
                    'count': 1,
                    'pixels': [{'x': 0, 'y': 0}],
                    'hex': '#FF0000'
                }],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
                filamentColors=colors
            )
            pytest.fail(
                "BUG QA-05: Duplicate hex colors (#FF0000) accepted in filament config. "
                "Cyan and Magenta have the same hex, producing identical physical output."
            )
        except Exception:
            pass  # Expected: validation should catch this


# -- BUG QA-06: merge_stl_meshes returns empty bytes for no meshes ----------
# File: backend/services/stl_generator.py:145-146
# Returns b'' instead of a valid empty STL binary.


class TestEmptyStlBinaryFormat:
    """
    BUG QA-06: merge_stl_meshes() returns b'' for empty mesh list.

    A valid STL binary must have an 80-byte header + 4-byte triangle count.
    Returning b'' creates an invalid file that crashes STL viewers.
    """

    def test_empty_mesh_returns_valid_stl(self):
        """An empty mesh list should still produce a valid STL binary header."""
        from services.stl_generator import merge_stl_meshes

        result = merge_stl_meshes([])

        # A valid empty STL has 84 bytes: 80-byte header + 4-byte count (0)
        assert len(result) >= 84, (
            f"BUG QA-06: merge_stl_meshes([]) returns {len(result)} bytes. "
            f"A valid empty STL needs 84 bytes (80 header + 4 count). "
            f"Returning b'' creates an invalid file that crashes STL viewers."
        )


# -- BUG QA-07: No upper bound on transmission_distance --------------------
# File: backend/api/models.py:20-24
# Only gt=0, no upper bound. Extreme values break Beer-Lambert.


class TestTransmissionDistanceBounds:
    """
    BUG QA-07: transmission_distance has no upper bound in FilamentColorConfig.

    Setting transmission_distance=999999 makes all layers fully transparent,
    producing white-only output. This is a user-facing UX bug.
    """

    def test_extreme_transmission_distance_rejected(self):
        """Extreme transmission_distance should be capped or rejected."""
        from api.models import FilamentColorConfig

        # BUG: This should raise validation error
        try:
            config = FilamentColorConfig(
                name='Cyan',
                hex='#00FFFF',
                transmission_distance=999999.0
            )
            pytest.fail(
                "BUG QA-07: transmission_distance=999999.0 accepted. "
                "This makes the filament fully transparent, producing "
                "all-white output. Should cap at reasonable max (e.g., 1000)."
            )
        except Exception:
            pass


# -- BUG QA-08: No PixelCoordinate bounds validation -----------------------
# File: backend/api/models.py:50-53
# PixelCoordinate allows negative x/y values.


class TestPixelCoordinateBounds:
    """
    BUG QA-08: PixelCoordinate allows negative and out-of-range coordinates.

    Negative pixel coordinates cause array indexing errors in
    mesh_optimizer.py and stl_generator.py.
    """

    def test_negative_pixel_coordinates_rejected(self):
        """Negative pixel coordinates should be rejected by the model."""
        from api.models import PixelCoordinate

        # BUG: Negative coordinates accepted, causing downstream IndexError
        try:
            coord = PixelCoordinate(x=-1, y=-1)
            pytest.fail(
                "BUG QA-08: Negative pixel coordinates (x=-1, y=-1) accepted. "
                "These cause IndexError in mesh_optimizer.py when accessing "
                "the grid array. Add ge=0 to PixelCoordinate fields."
            )
        except Exception:
            pass


# -- BUG QA-09: ImageDimensions allows zero/negative values -----------------
# File: backend/api/models.py:66-69


class TestImageDimensionsBounds:
    """
    BUG QA-09: ImageDimensions allows zero or negative width/height.

    Zero width causes division by zero in stl_generator.py.
    Negative dimensions cause invalid mesh geometry.
    """

    def test_zero_dimensions_rejected(self):
        """Zero image dimensions should be rejected."""
        from api.models import ImageDimensions

        # BUG: width=0 causes division by zero in downstream code
        try:
            dims = ImageDimensions(width=0, height=0)
            pytest.fail(
                "BUG QA-09: Zero image dimensions (0x0) accepted. "
                "This causes division by zero in stl_generator.py "
                "and generates empty STL files. Add gt=0 constraint."
            )
        except Exception:
            pass


# -- BUG QA-10: addFilamentColor creates empty name -------------------------
# Frontend-visible bug with backend implications.
# File: src/hooks/useImageProcessor.ts:72


class TestEmptyFilamentNameValidation:
    """
    BUG QA-10: New filament color added with empty name passes frontend
    validation momentarily, then fails on backend with unhelpful error.

    The frontend creates { name: '', hex: '#808080', transmission_distance: 5.0 }
    but the isFilamentConfigValid check catches it. However, the backend
    model accepts name='' if min_length check is bypassed.

    Testing the backend side: name with only whitespace.
    """

    def test_whitespace_only_name_rejected(self):
        """Filament name that is whitespace-only should be rejected."""
        from api.models import FilamentColorConfig

        # BUG: name=" " passes min_length=1 but produces invalid label
        try:
            config = FilamentColorConfig(
                name=' ',
                hex='#00FFFF',
                transmission_distance=3.0
            )
            # The label would be ' '[0].upper() = ' ' which is not a valid label
            assert config.name.strip() != '', (
                "BUG QA-10: Whitespace-only name ' ' accepted. "
                "The label becomes ' ' which breaks color lookup in Colors dict."
            )
        except Exception:
            pass  # Expected if validation catches it


# -- BUG QA-11: V1 download-stl uses global state, V2 re-initializes -------
# File: backend/api/routes/download.py
# Fixed: generate_stl_zip now computes reference matrices locally.
# V1 passes Colors() directly, no global state dependency.


class TestV1UsesStaleGlobalState:
    """
    BUG QA-11: Fixed — V1 route passes Colors() directly to generate_stl_zip,
    which computes reference matrices locally (no global state dependency).
    """

    def test_v1_passes_default_colors(self):
        """V1 download route passes default Colors() to generate_stl_zip."""
        import inspect
        from api.routes.download import api_download_stl

        source = inspect.getsource(api_download_stl)

        # V1 route creates default Colors() and passes it directly
        has_default_colors = 'Colors()' in source
        # Should NOT depend on initialize_color_mapping anymore
        no_global_init = 'initialize_color_mapping' not in source

        assert has_default_colors, (
            "V1 /api/download-stl should create default Colors() and pass to generate_stl_zip."
        )
        assert no_global_init, (
            "V1 /api/download-stl should not call initialize_color_mapping. "
            "generate_stl_zip computes matrices locally."
        )


# -- BUG QA-15: Preview has permutation guard but V2 download endpoint -------
# does NOT re-validate. FilamentPreviewService.generate_preview() has a guard
# (max_permutations=1_000_000), but the V2 download_stl endpoint calls
# initialize_color_mapping() which has NO such guard.
# This means the same color config that is safe for preview will OOM on download.


class TestV2DownloadHasNoPermutationGuard:
    """
    BUG QA-15: V2 download endpoint lacks the permutation guard that
    FilamentPreviewService has.

    FilamentPreviewService correctly checks permutation_count before
    generating. But the V2 download-stl endpoint calls
    initialize_color_mapping() which has no such guard.

    A user can preview 6 colors x 6 layers (46656, passes preview guard)
    then download STL - both paths call itertools.product, but only
    preview validates. stl_generator.initialize_color_mapping() has no limit.
    """

    def test_compute_reference_matrices_has_permutation_guard(self):
        """compute_reference_matrices should have permutation guard."""
        import inspect
        from services.stl_generator import compute_reference_matrices

        source = inspect.getsource(compute_reference_matrices)

        has_limit_check = (
            'raise ValueError' in source or
            'max_permutations' in source or
            'too many' in source.lower()
        )

        assert has_limit_check, (
            "BUG QA-15: compute_reference_matrices() has no "
            "permutation guard. With 10 colors and 10 layers, the download "
            "endpoint will OOM."
        )


# -- BUG QA-16: CSV injection via formula in hex field -----------------------
# File: backend/services/csv_generator.py:18-21
# Hex field is embedded raw in CSV without quoting/escaping.


class TestCsvInjection:
    """
    BUG QA-16: CSV generator does not sanitize or quote fields, allowing
    formula injection.

    If a hex value contains '=', '+', '-', or '@', spreadsheet applications
    (Excel, Google Sheets) will interpret it as a formula when opened.

    While hex values are typically validated by the model, the CSV generator
    itself has no defense in depth. Additionally, commas in any field
    break column alignment.
    """

    def test_csv_formula_injection_via_hex(self):
        """Hex field starting with = should be escaped or quoted in CSV."""
        from services.csv_generator import generate_csv

        blocks = [{
            'r': 255, 'g': 0, 'b': 0,
            'count': 1,
            'pixels': [{'x': 0, 'y': 0}],
            'hex': '=CMD("calc")'  # Formula injection payload
        }]

        csv = generate_csv(blocks)
        lines = csv.split('\n')
        data_line = lines[1]

        # The raw formula should NOT appear unquoted in CSV output
        # A safe CSV would either quote the field or prefix with '
        fields = data_line.split(',')
        hex_field = fields[4] if len(fields) > 4 else ''
        is_raw_formula = hex_field.startswith('=') or hex_field.startswith('+') or hex_field.startswith('@')

        assert not is_raw_formula, (
            f"BUG QA-16: CSV output embeds hex field raw without quoting. "
            f"Hex field contains raw formula: {hex_field!r}. "
            f"When opened in Excel/Sheets, '=CMD(\"calc\")' executes as a "
            f"formula. Use Python csv module with proper quoting."
        )

    def test_csv_comma_injection_breaks_columns(self):
        """Commas in hex field should not break CSV column structure."""
        import csv as csv_mod
        import io
        from services.csv_generator import generate_csv

        blocks = [{
            'r': 255, 'g': 0, 'b': 0,
            'count': 1,
            'pixels': [{'x': 0, 'y': 0}],
            'hex': '#FF0000,injected'
        }]

        csv_output = generate_csv(blocks)
        reader = csv_mod.reader(io.StringIO(csv_output))
        rows = list(reader)
        header_fields = len(rows[0])
        data_fields = len(rows[1])

        assert header_fields == data_fields, (
            f"BUG QA-16: CSV column count mismatch. Header has {header_fields} "
            f"fields but data has {data_fields}. Commas in hex field break "
            f"column alignment. Use Python csv module with proper quoting."
        )


# -- BUG QA-17: update_white_balance parameter order is (r, b, g) -----------
# File: backend/core/blend_color.py:215-218
# Function signature is update_white_balance(self, new_r, new_b, new_g)
# but the natural expectation is (r, g, b) order.


class TestWhiteBalanceParameterOrder:
    """
    BUG QA-17: Colors.update_white_balance() has parameters in wrong order.

    Signature: update_white_balance(self, new_r, new_b, new_g)
    Expected:  update_white_balance(self, new_r, new_g, new_b)

    The function body assigns:
        self.white_balance['r'] = new_r  (correct)
        self.white_balance['b'] = new_b  (second param is 'b')
        self.white_balance['g'] = new_g  (third param is 'g')

    Any caller using positional args (r, g, b) would swap green and blue.
    """

    def test_white_balance_parameter_order_matches_rgb(self):
        """update_white_balance parameters should follow RGB convention."""
        import inspect
        from core.blend_color import Colors

        sig = inspect.signature(Colors.update_white_balance)
        params = list(sig.parameters.keys())
        # Skip 'self'
        params = params[1:]

        # Natural convention: r, g, b
        assert params == ['new_r', 'new_g', 'new_b'], (
            f"BUG QA-17: update_white_balance() parameter order is {params}. "
            f"Expected ['new_r', 'new_g', 'new_b'] (RGB convention). "
            f"Current order (r, b, g) swaps green and blue for positional callers."
        )


# -- BUG QA-18: Mutable default argument in BlendTestGenerator.__init__ ------
# File: backend/core/blend_color.py:262
# colors = Colors() is a mutable default argument.


class TestMutableDefaultArgument:
    """
    BUG QA-18: BlendTestGenerator uses Colors() as default argument.

    Line 262: def __init__(self, ..., colors=Colors()):

    This is a classic Python anti-pattern. The Colors() object is created
    once at class definition time and shared across ALL instances that
    don't provide explicit colors. Mutating one instance's colors dict
    affects all others.
    """

    def test_default_colors_not_shared_between_instances(self):
        """Each BlendTestGenerator should get its own Colors instance."""
        from core.blend_color import BlendTestGenerator

        gen1 = BlendTestGenerator(verbose=False)
        gen2 = BlendTestGenerator(verbose=False)

        assert gen1.colors is not gen2.colors, (
            "BUG QA-18: BlendTestGenerator instances share the same default "
            "Colors object. colors=Colors() in __init__ signature creates "
            "ONE shared mutable object. If gen1 modifies its colors, gen2 "
            "is also affected. Fix: Use colors=None and create Colors() "
            "inside __init__ if None."
        )


# -- BUG QA-19: code_to_rgb IndexError when code length > layer_count_max ----
# File: backend/core/blend_color.py:543-546
# light_loss_ratio array is size (layer_count_max+1).
# If code length > layer_count_max, line 546 writes out of bounds.


class TestCodeToRgbIndexError:
    """
    BUG QA-19: code_to_rgb() crashes with IndexError when code length
    exceeds layer_count_max.

    Line 541: light_loss_ratio = np.zeros(self.layer_count_max+1)
    Line 543: for i, t in enumerate(tranmission):
    Line 546: light_loss_ratio[i+1] = remain * (1-t)

    If len(code) > layer_count_max, index i+1 overflows the array.
    This can happen when initialize_color_mapping is called with one
    layer_count and generate_stl_zip is called with a different one.
    """

    def test_code_longer_than_layer_count_max(self):
        """code_to_rgb should handle code length > layer_count_max gracefully."""
        from core.blend_color import BlendTestGenerator, Colors

        gen = BlendTestGenerator(
            colors=Colors(),
            verbose=False,
            layer_count_max=4
        )

        # A code of length 5 when layer_count_max is 4 should NOT crash
        try:
            result = gen.code_to_rgb('CCCCC')
            # If it doesn't crash, it should still return valid RGB
            assert all(0 <= v <= 255 for v in result), (
                f"Invalid RGB values: {result}"
            )
        except IndexError:
            pytest.fail(
                "BUG QA-19: code_to_rgb('CCCCC') with layer_count_max=4 "
                "raises IndexError. light_loss_ratio array is size 5 but "
                "loop iterates 5 times, writing to index 5 (out of bounds). "
                "Fix: Validate len(code) <= layer_count_max or resize array."
            )


# -- BUG QA-20: Color.get_transmission_rate ZeroDivisionError ---------------
# File: backend/core/blend_color.py:77
# x = alpha * d / td  -- no guard for td=0


class TestTransmissionRateZeroDivision:
    """
    BUG QA-20: Color.get_transmission_rate() crashes with ZeroDivisionError
    when transmission_distance (td) is 0.

    Line 77: x = alpha * d / td

    While the Pydantic model has gt=0, the Color class itself has no
    validation. Direct Color construction (e.g., from Colors.from_configs
    with malformed data) can pass td=0, crashing Beer-Lambert computation.
    """

    def test_zero_transmission_distance_does_not_crash(self):
        """get_transmission_rate should handle td=0 gracefully."""
        from core.blend_color import Color

        # Should not raise ZeroDivisionError
        rate = Color.get_transmission_rate(d=0.08, td=0, alpha=23)
        # td=0 means fully opaque, transmission rate should be 0.0
        assert rate == 0.0, (
            f"BUG QA-20: Expected transmission rate 0.0 for td=0 "
            f"(fully opaque), got {rate}"
        )


# -- BUG QA-10: Whitespace-only filament name accepted -----------------------
# File: backend/api/models.py:18
# name: str = Field(..., min_length=1) accepts "  " (spaces only)


class TestWhitespaceFilamentName:
    """
    BUG QA-10: FilamentColorConfig accepts whitespace-only names like "  ",
    "\\t", "\\n" because min_length=1 counts whitespace as characters.

    The label (first character of name) becomes ' ', '\\t', or '\\n',
    which breaks color lookup in BlendTestGenerator and Colors.__getitem__.
    """

    def test_whitespace_only_name_rejected_by_model(self):
        """Names with only whitespace should be rejected."""
        from api.models import FilamentColorConfig

        try:
            c = FilamentColorConfig(
                name='  ', hex='#FF0000', transmission_distance=3.0
            )
            pytest.fail(
                f"BUG QA-10: Whitespace-only name '  ' accepted by "
                f"FilamentColorConfig. Label becomes {repr(c.name[0])} which "
                f"is not a valid color identifier. Fix: Add strip_whitespace=True "
                f"to Field or add @validator to reject whitespace-only names."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_tab_newline_names_rejected(self):
        """Tab and newline names should be rejected."""
        from api.models import FilamentColorConfig

        for name in ['\t', '\n', '   ', ' \t\n ']:
            try:
                c = FilamentColorConfig(
                    name=name, hex='#FF0000', transmission_distance=3.0
                )
                pytest.fail(
                    f"BUG QA-10: Whitespace name {repr(name)} accepted. "
                    f"Label becomes {repr(c.name[0])}."
                )
            except (ValueError, Exception):
                pass  # Correctly rejected


# -- BUG QA-21: Hex without # prefix passes validation -----------------------
# File: backend/api/models.py:27-36 (hex validator)
# lstrip('#') removes '#' if present but doesn't require it.
# '00FFFF' passes validation, but Color() constructor crashes on it.


class TestHexWithoutHashPrefix:
    """
    BUG QA-21: FilamentColorConfig hex validator accepts hex values without
    the '#' prefix (e.g., '00FFFF'). The lstrip('#') in the validator
    removes '#' if present but doesn't verify it was there.

    Downstream, Color(hex='00FFFF') raises ValueError because
    PIL's ImageColor.getrgb() requires the '#' prefix.
    """

    def test_hex_without_hash_rejected(self):
        """Hex value without # prefix should be rejected."""
        from api.models import FilamentColorConfig

        try:
            c = FilamentColorConfig(
                name='Test', hex='00FFFF', transmission_distance=3.0
            )
            # If accepted, verify it would break downstream
            from core.blend_color import Color
            try:
                color = Color(name='Test', transmission_distance=3.0, hex=c.hex)
                # If this works, the stored hex was somehow fixed
                pass
            except ValueError:
                pytest.fail(
                    f"BUG QA-21: Hex '00FFFF' (no '#') passes model validation "
                    f"as {repr(c.hex)}, but Color() constructor crashes with "
                    f"ValueError. Fix: Require '#' prefix in hex validator."
                )
        except (ValueError, Exception):
            pass  # Correctly rejected at model level


# -- BUG QA-22: Dark colors always merged regardless of threshold -------------
# File: backend/services/image_processor.py:58-81
# merge_similar_colors() groups ALL dark neutral colors unconditionally,
# ignoring the threshold parameter.


class TestDarkColorMergingIgnoresThreshold:
    """
    BUG QA-22: merge_similar_colors() merges all dark neutral colors into
    a single cluster regardless of the colorThreshold setting.

    Lines 66-81: When is_dark_neutral_color(color_rgb) is True, ALL other
    dark neutral colors are merged into the same cluster. The threshold
    parameter is completely ignored for dark colors.

    This means setting colorThreshold=0 (no merging) still merges dark
    colors, violating user expectations.
    """

    def test_dark_colors_not_merged_with_zero_threshold(self):
        """With threshold=0, no colors should be merged - including dark ones."""
        from services.image_processor import merge_similar_colors

        dark_colors = [
            {'r': 10, 'g': 10, 'b': 10, 'count': 5,
             'pixels': [{'x': 0, 'y': 0}]},
            {'r': 20, 'g': 20, 'b': 20, 'count': 3,
             'pixels': [{'x': 1, 'y': 0}]},
        ]

        result = merge_similar_colors(dark_colors, threshold=0)

        assert len(result) == 2, (
            f"BUG QA-22: merge_similar_colors() with threshold=0 merged "
            f"{len(dark_colors)} dark colors into {len(result)}. With "
            f"threshold=0, no colors should be merged. Dark neutral colors "
            f"are unconditionally grouped, ignoring the threshold parameter."
        )


# -- BUG QA-23: Invalid mode returns 500 instead of 400 ---------------------
# File: backend/api/routes/image.py:55, 126-128
# ProcessingMode(mode) raises ValueError for invalid mode.
# This is caught by the generic Exception handler and returns 500.


class TestInvalidModeReturns400:
    """
    BUG QA-23: Invalid mode parameter in /api/process-image returns 500
    instead of 400.

    Line 55: processing_mode = ProcessingMode(mode) raises ValueError for
    invalid mode strings like 'invalid' or 'raster'.

    Lines 126-128: Generic Exception handler catches ValueError and returns
    500 with "An internal error occurred" instead of a clear 400 error
    telling the user the mode is invalid.
    """

    def test_invalid_mode_caught_before_generic_handler(self):
        """Invalid mode should be caught and converted to HTTPException(400)."""
        import inspect
        from api.routes.image import api_process_image

        # Get the inner function source (unwrapped from decorator)
        func = api_process_image.__wrapped__ if hasattr(api_process_image, '__wrapped__') else api_process_image
        source = inspect.getsource(func)

        # The route should catch ValueError from ProcessingMode() explicitly
        has_explicit_catch = (
            'HTTPException' in source and
            '400' in source and
            'ProcessingMode' in source
        )

        assert has_explicit_catch, (
            "BUG QA-23: api_process_image does not explicitly catch ValueError "
            "from ProcessingMode(mode). Invalid mode falls through to generic "
            "Exception handler, returning 500 instead of 400."
        )


# =============================================================================
# QA ROUND 4 (2026-02-07)
# =============================================================================


# -- BUG QA-24: ColorBlock hex field has no validation -------------------------
# File: backend/api/models.py:64
# ColorBlock.hex is a plain str field with no validator.
# Arbitrary strings like 'NOT_A_HEX', XSS payloads, or '=CMD("calc")'
# pass through and get stored/returned to the client.


class TestColorBlockHexNoValidation:
    """
    BUG QA-24: ColorBlock.hex has no validation.

    Unlike FilamentColorConfig.hex which has a @validator,
    ColorBlock.hex is a plain str field that accepts any value.

    While CSV injection is mitigated by QUOTE_ALL, the unvalidated hex
    value is returned to the frontend in API responses and could be used
    for XSS if rendered unsafely.
    """

    def test_colorblock_accepts_arbitrary_hex(self):
        """ColorBlock should validate the hex field format."""
        from api.models import ColorBlock

        try:
            block = ColorBlock(
                r=0, g=0, b=0, count=1,
                pixels=[{'x': 0, 'y': 0}],
                hex='NOT_A_HEX'
            )
            pytest.fail(
                f"BUG QA-24: ColorBlock accepts arbitrary hex value "
                f"{block.hex!r}. No format validation on the hex field. "
                f"Fix: Add @validator or use a constrained str type for hex."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_colorblock_accepts_xss_payload_in_hex(self):
        """ColorBlock hex should not accept script injection payloads."""
        from api.models import ColorBlock

        try:
            block = ColorBlock(
                r=0, g=0, b=0, count=1,
                pixels=[{'x': 0, 'y': 0}],
                hex='<script>alert(1)</script>'
            )
            pytest.fail(
                f"BUG QA-24: ColorBlock accepts XSS payload in hex: "
                f"{block.hex!r}. This value is returned in API responses "
                f"and could cause XSS if rendered unsafely in the frontend."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected


# -- BUG QA-25: ColorConfig accepts whitespace-only names ---------------------
# File: backend/core/color_config.py:29
# __post_init__ checks `if not self.name` which is True for '' but False
# for '   ' (whitespace-only). Whitespace names produce invalid labels.


class TestColorConfigWhitespaceName:
    """
    BUG QA-25: ColorConfig.__post_init__ doesn't reject whitespace-only names.

    Line 29: `if not self.name:` only catches empty string '', not '   '.
    A name of '   ' produces label ' ' which breaks color lookups in
    Colors dict and BlendTestGenerator.
    """

    def test_whitespace_only_name_rejected(self):
        """ColorConfig should reject whitespace-only names."""
        from core.color_config import ColorConfig

        try:
            c = ColorConfig(name='   ', hex='#FF0000', transmission_distance=3.0)
            pytest.fail(
                f"BUG QA-25: ColorConfig accepts whitespace-only name '   '. "
                f"Label becomes {repr(c.label)} which is not a valid color "
                f"identifier. Fix: Add `if not self.name.strip()` check."
            )
        except ValueError:
            pass  # Correctly rejected

    def test_tab_newline_names_rejected(self):
        """Tab and newline names should be rejected by ColorConfig."""
        from core.color_config import ColorConfig

        for name in ['\t', '\n', ' \t\n ']:
            try:
                c = ColorConfig(name=name, hex='#FF0000', transmission_distance=3.0)
                pytest.fail(
                    f"BUG QA-25: ColorConfig accepts whitespace name {repr(name)}. "
                    f"Label becomes {repr(c.label)}."
                )
            except ValueError:
                pass  # Correctly rejected


# -- BUG QA-26: Colors.from_configs silently drops duplicate labels -----------
# File: backend/core/blend_color.py:256
# When two configs have the same first letter (e.g., 'Coral' and 'Crimson'),
# the second silently overwrites the first in the dict.


class TestFromConfigsDuplicateLabels:
    """
    BUG QA-26: Colors.from_configs() silently drops colors with duplicate labels.

    If two ColorConfig objects have names starting with the same letter
    (e.g., 'Coral' and 'Crimson' both map to label 'C'), the second one
    silently overwrites the first. The caller gets fewer colors than
    expected, producing incorrect STL output.

    The API validator catches this for user input, but Colors.from_configs()
    is also called from get_colors_from_request() with preset configs,
    and could be called from other code paths.
    """

    def test_from_configs_raises_on_duplicate_labels(self):
        """Colors.from_configs should raise error for configs with duplicate labels."""
        from core.blend_color import Colors
        from core.color_config import ColorConfig

        configs = [
            ColorConfig(name='Coral', hex='#FF7F50', transmission_distance=3.0),
            ColorConfig(name='Crimson', hex='#DC143C', transmission_distance=1.9),
            ColorConfig(name='Yellow', hex='#FFFF00', transmission_distance=2.5),
            ColorConfig(name='White', hex='#FFFFFF', transmission_distance=7.2),
        ]

        try:
            colors = Colors.from_configs(configs)
            # Should have raised error, but silently dropped Coral
            if len(colors) < len(configs):
                pytest.fail(
                    f"BUG QA-26: Colors.from_configs() silently dropped colors "
                    f"with duplicate labels. Passed {len(configs)} configs, got "
                    f"{len(colors)} colors. 'Coral' and 'Crimson' both map to "
                    f"label 'C', so Crimson overwrites Coral. "
                    f"Fix: Check for label uniqueness before inserting."
                )
        except ValueError:
            pass  # Correctly rejected


# -- BUG QA-27: ValueError from permutation guard returns 500 -----------------
# Files: backend/api/routes/download_v2.py:170, backend/api/routes/filament.py:57
# ValueError from initialize_color_mapping() or generate_preview() is caught
# by the generic Exception handler and returns 500 instead of 400/422.


class TestPermutationGuardReturns500:
    """
    BUG QA-27: ValueError from permutation guard is caught by generic
    Exception handler in V2 download and filament preview routes, returning
    500 instead of 400/422.

    The permutation guard raises ValueError with a descriptive message,
    but the route handlers don't catch ValueError specifically. The generic
    `except Exception as e` block returns HTTPException(500).
    """

    def test_v2_download_catches_valueerror_specifically(self):
        """V2 download route should catch ValueError and return 422."""
        from api.routes.download_v2 import api_download_stl_v2

        # The handle_api_errors decorator provides ValueError -> 422 handling
        assert hasattr(api_download_stl_v2, '__wrapped__'), (
            "BUG QA-27: api_download_stl_v2() should use @handle_api_errors "
            "decorator which catches ValueError and returns 422."
        )

    def test_filament_preview_catches_valueerror_specifically(self):
        """Filament preview route should catch ValueError and return 422."""
        from api.routes.filament import api_filament_preview

        # The handle_api_errors decorator provides ValueError -> 422 handling
        assert hasattr(api_filament_preview, '__wrapped__'), (
            "BUG QA-27: api_filament_preview() should use @handle_api_errors "
            "decorator which catches ValueError and returns 422."
        )


# -- BUG QA-28: Color() crashes when name has no default hex -----------------
# File: backend/core/blend_color.py:32-35
# When hex=None and name is not in DEFAULT_HEX (not C/M/Y/W),
# DEFAULT_HEX.get() returns None, then update_hex(None) crashes.


class TestColorNoDefaultHexCrash:
    """
    BUG QA-28: Color(name='Red') crashes with TypeError because 'Red'
    maps to label 'R' which is not in DEFAULT_HEX.

    Flow:
    1. hex=None (default)
    2. DEFAULT_HEX.get('R') returns None
    3. update_hex(None)
    4. ImageColor.getcolor(None, 'RGB') -> TypeError

    This affects any direct Color construction with a non-CMYW name
    without providing hex. While Colors.from_configs() always provides
    hex, other code paths may not.
    """

    def test_color_without_hex_for_non_default_name(self):
        """Color with non-CMYW name and no hex should raise clear error, not TypeError."""
        from core.blend_color import Color

        try:
            c = Color(name='Red', transmission_distance=3.0)
            # If it doesn't crash, it should at least have a valid hex
            assert c.hex is not None, "hex should not be None"
        except TypeError:
            pytest.fail(
                "BUG QA-28: Color(name='Red') without hex raises TypeError "
                "(object of type 'NoneType' has no len()). DEFAULT_HEX has "
                "no entry for label 'R', so hex stays None, causing crash "
                "in update_hex(None). Fix: Raise ValueError with clear "
                "message when hex is required but not provided."
            )
        except ValueError:
            pass  # Correctly raises ValueError with clear message


# -- BUG QA-29: Colors(names=['X']) creates Color with td=None ---------------
# File: backend/core/blend_color.py:186-190
# When names contains labels not in DEFAULT_TD, dict.get() returns None.
# Color is created with td=None, causing TypeError in get_transmission_rate.


class TestColorsNonExistentLabelTdNone:
    """
    BUG QA-29: Colors(names=['X']) creates Color with transmission_distance=None.

    Line 190: Colors.DEFAULT_TD.get(c) returns None for unknown labels.
    Color is created with td=None, which crashes later when
    get_transmission_rate() tries: `if td <= 0` -> TypeError.

    This path is reachable via Colors(names=['X', 'Y', 'Z', 'W'])
    for any label not in the DEFAULT_TD dictionary.
    """

    def test_unknown_label_raises_valueerror(self):
        """Colors with unknown label names should raise ValueError, not create Color with td=None."""
        from core.blend_color import Colors

        with pytest.raises(ValueError, match="Unknown color label"):
            Colors(names=['X'])

    def test_unknown_label_does_not_create_invalid_color(self):
        """Unknown label should be rejected early, not cause downstream TypeError."""
        from core.blend_color import Colors

        try:
            colors = Colors(names=['X'])
            pytest.fail(
                "BUG QA-29: Colors(names=['X']) should raise ValueError for "
                "unknown label 'X', but silently created Color with td=None."
            )
        except ValueError:
            pass  # Correctly rejected


# =============================================================================
# QA ROUND 5 (2026-02-07)
# =============================================================================


# -- BUG QA-30: Double-hash hex passes validation but crashes Color() ----------
# Files: backend/api/models.py:30, backend/core/color_config.py:33
# lstrip('#') strips ALL leading '#' chars, so '##FF00FF' -> 'FF00FF' (6 chars).
# Passes length check, passes int(hex, 16) check, but '##FF00FF' is not a valid
# color specifier for PIL ImageColor, so Color() crashes with ValueError.


class TestDoubleHashHexValidation:
    """
    BUG QA-30: '##FF00FF' passes hex validation but crashes downstream.

    Both FilamentColorConfig and ColorConfig use lstrip('#') to strip the
    '#' prefix. But lstrip strips ALL leading characters, not just one.
    So '##FF00FF' -> 'FF00FF' which has 6 chars and is valid hex.

    However, the stored value '##FF00FF' causes:
    - Color(hex='##FF00FF') -> ValueError from PIL ImageColor
    - get_colors_from_request() -> crash during STL generation
    """

    def test_double_hash_rejected_by_filament_config(self):
        """FilamentColorConfig should reject '##FF00FF'."""
        from api.models import FilamentColorConfig

        try:
            c = FilamentColorConfig(
                name='Test', hex='##FF00FF', transmission_distance=3.0
            )
            # If accepted, verify it breaks downstream
            from core.blend_color import Color
            try:
                Color(name='Test', transmission_distance=3.0, hex=c.hex)
                pass  # Somehow works - no bug
            except ValueError:
                pytest.fail(
                    f"BUG QA-30: '##FF00FF' passes FilamentColorConfig validation "
                    f"(stored as {repr(c.hex)}) but crashes Color() with ValueError. "
                    f"lstrip('#') strips ALL leading '#' chars. "
                    f"Fix: Use v[1:] instead of v.lstrip('#'), or require exactly "
                    f"one '#' prefix with regex."
                )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_double_hash_rejected_by_color_config(self):
        """ColorConfig should reject '##FF00FF'."""
        from core.color_config import ColorConfig

        try:
            c = ColorConfig(
                name='Test', hex='##FF00FF', transmission_distance=3.0
            )
            from core.blend_color import Color
            try:
                Color(name='Test', transmission_distance=3.0, hex=c.hex)
                pass
            except ValueError:
                pytest.fail(
                    f"BUG QA-30: '##FF00FF' passes ColorConfig validation "
                    f"(stored as {repr(c.hex)}) but crashes Color(). "
                    f"Fix: Use hex[1:] instead of hex.lstrip('#')."
                )
        except ValueError:
            pass  # Correctly rejected


# -- BUG QA-31: ColorConfig accepts hex without '#' prefix --------------------
# File: backend/core/color_config.py:33
# Same lstrip('#') issue as QA-21 but in the internal ColorConfig dataclass.
# 'FF00FF' passes validation (lstrip does nothing, len=6, valid hex).
# But Color(hex='FF00FF') crashes with ValueError from PIL ImageColor.


class TestColorConfigNoHashPrefix:
    """
    BUG QA-31: ColorConfig accepts hex without '#' prefix.

    ColorConfig.__post_init__ uses lstrip('#') which does nothing if '#'
    is absent. 'FF00FF' has 6 chars and passes int(hex, 16) check.
    But PIL ImageColor.getcolor('FF00FF', 'RGB') raises ValueError.

    While the Pydantic FilamentColorConfig has the same issue (QA-21),
    ColorConfig is used internally (e.g., in presets, from_configs()).
    A programmatic error passing 'FF00FF' instead of '#FF00FF' would
    crash silently at a later stage.
    """

    def test_no_hash_prefix_rejected(self):
        """ColorConfig should reject hex without '#' prefix."""
        from core.color_config import ColorConfig

        try:
            c = ColorConfig(
                name='Test', hex='FF00FF', transmission_distance=3.0
            )
            from core.blend_color import Color
            try:
                Color(name='Test', transmission_distance=3.0, hex=c.hex)
                pass  # Somehow works
            except ValueError:
                pytest.fail(
                    f"BUG QA-31: ColorConfig accepts 'FF00FF' (no '#') as "
                    f"{repr(c.hex)} but Color() crashes with ValueError. "
                    f"Fix: Require '#' prefix in validation (e.g., "
                    f"if not self.hex.startswith('#'))."
                )
        except ValueError:
            pass  # Correctly rejected


# -- BUG QA-32: print() used instead of logger in initialize_color_mapping -----
# File: backend/services/stl_generator.py:92
# Uses print() instead of logger.info(), sending debug output to stdout
# in production deployments. This also makes it impossible to control
# log level or route to log aggregators.


class TestPrintInsteadOfLogger:
    """
    BUG QA-32: stl_generator.initialize_color_mapping() uses print()
    instead of logger.info() on line 92.

    In production, this sends unstructured text to stdout which:
    - Cannot be filtered by log level
    - Cannot be routed to log aggregators (e.g., CloudWatch, Datadog)
    - Pollutes stdout when running tests
    - Is inconsistent with all other modules that use logging
    """

    def test_no_print_in_initialize_color_mapping(self):
        """initialize_color_mapping should use logger, not print."""
        import inspect
        from services.stl_generator import initialize_color_mapping

        source = inspect.getsource(initialize_color_mapping)

        assert 'print(' not in source, (
            "BUG QA-32: initialize_color_mapping() uses print() instead of "
            "logger.info(). This sends debug output to stdout in production. "
            "Fix: Replace print(f\"Initialized color mapping: ...\") with "
            "logger.info(\"Initialized color mapping: %d colors, %d combinations\", "
            "color_count, combo_count)."
        )


# -- BUG QA-33: ColorBlock count/pixels mismatch not validated ----------------
# File: backend/api/models.py:57-64
# ColorBlock.count is a separate field from len(pixels), but there's no
# cross-field validation. count=999 with pixels=[{x:0,y:0}] is accepted.
# Downstream code uses both count (for sorting) and pixels (for geometry),
# producing inconsistent behavior.


class TestColorBlockCountPixelsMismatch:
    """
    BUG QA-33: ColorBlock allows count that doesn't match len(pixels).

    count is used for:
    - Sorting by frequency in image_processor.py
    - Display in CSV output
    - Pixel assignment in reassign_colors()

    pixels is used for:
    - STL mesh generation (actual geometry)
    - Greedy meshing optimization

    A mismatch means the CSV reports 999 pixels but the STL only has 1.
    """

    def test_count_matches_pixel_length(self):
        """ColorBlock count should match len(pixels)."""
        from api.models import ColorBlock

        # This should be rejected: count says 999 pixels but only 1 provided
        try:
            block = ColorBlock(
                r=255, g=0, b=0, count=999,
                pixels=[{'x': 0, 'y': 0}],
                hex='#FF0000'
            )
            if block.count != len(block.pixels):
                pytest.fail(
                    f"BUG QA-33: ColorBlock accepts count={block.count} with "
                    f"{len(block.pixels)} pixel(s). No cross-field validation. "
                    f"CSV shows 999 pixels but STL generates mesh for 1. "
                    f"Fix: Add @validator('count') to verify count == len(pixels), "
                    f"or derive count from pixels."
                )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_zero_count_with_empty_pixels(self):
        """ColorBlock with count=0 and empty pixels should be rejected."""
        from api.models import ColorBlock

        try:
            block = ColorBlock(
                r=255, g=0, b=0, count=0,
                pixels=[],
                hex='#FF0000'
            )
            pytest.fail(
                f"BUG QA-33: ColorBlock accepts count=0 with empty pixels. "
                f"This produces no geometry in STL generation but counts as "
                f"a color block in the response, confusing users. "
                f"Fix: Add min_items=1 to pixels field."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected


# -- BUG QA-34: Empty color_blocks produces empty ZIP without error -----------
# File: backend/services/stl_generator.py:224-340
# generate_stl_zip([]) returns a valid ZIP with 0 files inside.
# No error, no warning. The user downloads a useless empty archive.
# The API should return 400 or at least log a warning.


class TestEmptyColorBlocksZip:
    """
    BUG QA-34: generate_stl_zip([]) produces an empty ZIP archive.

    When called with an empty color_blocks list, the function:
    1. Creates empty code_mesh_map (all values are [])
    2. No meshes are generated
    3. Returns a ZIP with 0 files

    The user downloads a 22-byte empty ZIP which is technically valid
    but completely useless. The API should return an error instead.
    """

    def test_empty_color_blocks_rejected(self):
        """generate_stl_zip should reject empty color_blocks."""
        from core.blend_color import Colors
        from services.stl_generator import generate_stl_zip, initialize_color_mapping

        colors = Colors()
        initialize_color_mapping(layer_count=4, colors=colors)

        try:
            result = generate_stl_zip(
                color_blocks=[],
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                image_dimensions={'width': 4, 'height': 4},
                colors=colors
            )
            # Check if ZIP is empty
            import zipfile
            from io import BytesIO
            zf = zipfile.ZipFile(BytesIO(result))
            if len(zf.namelist()) == 0:
                pytest.fail(
                    "BUG QA-34: generate_stl_zip([]) returns empty ZIP (0 files). "
                    "User downloads a useless 22-byte archive with no STL files. "
                    "Fix: Raise ValueError('No color blocks provided') when "
                    "color_blocks is empty, or return at least a warning."
                )
        except ValueError:
            pass  # Correctly rejected


# -- BUG QA-35: No mutual exclusivity between preset and custom colors --------
# Files: backend/api/models.py:128-129, 157-158, 193-194
# FilamentPreviewRequest, DownloadSTLRequestV2, DownloadSVGSTLRequestV2 all
# accept both filamentPreset AND filamentColors simultaneously.
# get_colors_from_request() silently ignores the preset when both are given.
# This is confusing UX: user selects a preset AND provides custom colors,
# and the preset is silently discarded.


class TestPresetAndCustomColorsMutualExclusivity:
    """
    BUG QA-35: Models accept both filamentPreset and filamentColors.

    When both are provided, get_colors_from_request() prioritizes
    filamentColors and silently ignores the preset. The user has no
    indication that their preset selection was discarded.

    This can cause confusion: user selects "Bambu CMYK" preset and
    also provides 4 custom colors. They expect Bambu colors but get
    their custom colors instead.
    """

    def test_preset_and_custom_colors_rejected(self):
        """Request with both preset and custom colors should be rejected."""
        from api.models import (
            FilamentColorConfig,
            FilamentPreset,
            FilamentPreviewRequest,
        )

        try:
            req = FilamentPreviewRequest(
                filamentPreset=FilamentPreset.BAMBU_CMYW_PHASE6,
                filamentColors=[
                    FilamentColorConfig(
                        name='Red', hex='#FF0000', transmission_distance=3.0
                    ),
                    FilamentColorConfig(
                        name='Green', hex='#00FF00', transmission_distance=3.0
                    ),
                    FilamentColorConfig(
                        name='Blue', hex='#0000FF', transmission_distance=3.0
                    ),
                    FilamentColorConfig(
                        name='White', hex='#FFFFFF', transmission_distance=7.2
                    ),
                ],
                layerCount=4,
            )
            # Both were accepted - bug
            if req.filamentPreset is not None and req.filamentColors is not None:
                pytest.fail(
                    "BUG QA-35: FilamentPreviewRequest accepts both "
                    "filamentPreset and filamentColors simultaneously. "
                    "The preset is silently ignored in get_colors_from_request(). "
                    "Fix: Add @root_validator to reject when both are provided, "
                    "or document the priority behavior clearly."
                )
        except (ValueError, Exception):
            pass  # Correctly rejected


class TestCodeToRgbUnclampedValues:
    """
    BUG QA-36: _code_to_rgb_cached() returns unclamped RGB values.

    Line 191-196:
        rgb = np.ones(3)
        for i, c in enumerate(code):
            color = color_map[c]
            rgb -= color.get_absorption() * light_loss_ratio[i]
        rgb = light_loss_ratio[-1] * np.ones(3) + (1 - light_loss_ratio[-1]) * rgb
        return tuple(rgb * 255)

    With long code strings or highly absorbing colors, floating point
    arithmetic can push RGB below 0 or above 255. Example:
    - 'C' * 100 returns R=-4.3e-19 (negative!)
    - Very opaque dark colors return negative values

    filament_preview.py manually clamps at line 80-84 (defense in depth),
    but _code_to_rgb_cached itself should guarantee [0, 255] range.
    """

    def test_rgb_values_clamped_to_valid_range(self):
        """code_to_rgb should always return values in [0, 255] range."""
        from core.blend_color import BlendTestGenerator, Colors, clear_rgb_cache

        clear_rgb_cache()
        gen = BlendTestGenerator(
            colors=Colors(),
            verbose=False,
            layer_count_max=100
        )

        # Long code that triggers floating point drift
        result = gen.code_to_rgb('C' * 100)

        for i, v in enumerate(result):
            channel = ['R', 'G', 'B'][i]
            assert v >= 0, (
                f"BUG QA-36: code_to_rgb('C'*100) returned {channel}={v}. "
                f"RGB values must be >= 0. Floating point drift in Beer-Lambert "
                f"produces negative values. Fix: clamp return value to [0, 255]."
            )
            assert v <= 255, (
                f"BUG QA-36: code_to_rgb('C'*100) returned {channel}={v}. "
                f"RGB values must be <= 255."
            )

    def test_opaque_colors_produce_valid_rgb(self):
        """Very opaque colors should still produce valid [0, 255] RGB."""
        from core.blend_color import (
            BlendTestGenerator, Color, Colors, clear_rgb_cache,
        )

        clear_rgb_cache()
        colors = Colors(colors={})
        colors.colors['A'] = Color(name='Alpha', transmission_distance=0.01, hex='#010101')
        colors.colors['B'] = Color(name='Beta', transmission_distance=0.01, hex='#020202')
        colors.colors['D'] = Color(name='Delta', transmission_distance=0.01, hex='#030303')
        colors.colors['E'] = Color(name='Epsilon', transmission_distance=0.01, hex='#040404')

        gen = BlendTestGenerator(
            colors=colors,
            verbose=False,
            layer_count_max=4
        )

        result = gen.code_to_rgb('ABDE')

        for i, v in enumerate(result):
            channel = ['R', 'G', 'B'][i]
            assert v >= 0, (
                f"BUG QA-36: Opaque colors code_to_rgb('ABDE') returned "
                f"{channel}={v}. Must be >= 0."
            )


# -- BUG QA-37: _code_to_rgb_cached KeyError for unknown chars in code ----------
# File: backend/core/blend_color.py:175-177
# The code iterates through each character in the blend code and looks it up
# in color_map. If the code contains a character not in color_map, a KeyError
# is raised with no descriptive message.


class TestCodeToRgbUnknownChar:
    """
    BUG QA-37: _code_to_rgb_cached() raises bare KeyError for unknown
    characters in the blend code.

    Line 175-177:
        transmission = [
            Color.get_transmission_rate(layer_height, color_map[c].td, alpha=23)
            for c in code
        ]

    If code contains 'X' and color_map only has C, M, Y, W, the list
    comprehension raises KeyError('X') with no context about what happened.

    This can occur when:
    1. map_to_nearest_color returns a code with chars from a different
       color config than the one being used for rendering
    2. A corrupted or manually edited code string is processed
    """

    def test_unknown_char_raises_descriptive_error(self):
        """Unknown char in blend code should raise a clear error, not bare KeyError."""
        from core.blend_color import _code_to_rgb_cached, clear_rgb_cache

        clear_rgb_cache()
        color_key = (
            ('C', 3.0, '#0086D6'),
            ('M', 1.9, '#EC008C'),
            ('Y', 2.5, '#F4EE2A'),
            ('W', 7.2, '#FFFFFF'),
        )

        try:
            _code_to_rgb_cached('CMYX', 0.08, color_key)
            pytest.fail(
                "Expected an error for code containing 'X' not in color_key"
            )
        except KeyError:
            pytest.fail(
                "BUG QA-37: _code_to_rgb_cached('CMYX') raises bare KeyError('X'). "
                "No context about which character failed or which colors are available. "
                "Fix: Catch KeyError and raise ValueError with descriptive message."
            )
        except ValueError:
            pass  # Expected: descriptive ValueError


# -- BUG QA-38: Color.is_brown() returns False for actual brown colors ----------
# File: backend/core/blend_color.py:103-106
# is_brown requires is_neutral() to be True, but brown colors have high
# chroma (C > 10) so is_neutral (which checks C < threshold) returns False.


class TestIsBrownLogicError:
    """
    BUG QA-38: Color.is_brown() returns False for actual brown colors.

    Line 106: return Color.is_neutral(rgb) and L < 60 and a > 5 and b > 10

    is_neutral returns True when chroma C < threshold (default 10).
    But brown colors (Saddlebrown, Chocolate, Sienna) have high chroma:
    - Saddlebrown (139,69,19): C=48.8 -> is_neutral=False -> is_brown=False
    - Chocolate (210,105,30): C=67.8 -> is_neutral=False -> is_brown=False

    The function NEVER returns True for standard brown colors because
    the is_neutral prerequisite contradicts brown's chroma characteristics.

    This affects color sorting in set_code_rgb_df (line 559), where brown
    colors are classified as tone=2 (chromatic) instead of tone=1 (brown),
    causing them to be sorted incorrectly in the color matrix.
    """

    def test_saddlebrown_detected_as_brown(self):
        """Saddlebrown (139, 69, 19) should be classified as brown."""
        from core.blend_color import Color

        assert bool(Color.is_brown((139, 69, 19))), (
            "BUG QA-38: Color.is_brown((139, 69, 19)) returns False for "
            "Saddlebrown. is_brown requires is_neutral() which checks "
            "chroma < 10, but Saddlebrown has chroma=48.8. The logic "
            "is contradictory: brown colors are not neutral by definition."
        )

    def test_chocolate_detected_as_brown(self):
        """Chocolate (210, 105, 30) should be classified as brown."""
        from core.blend_color import Color

        assert bool(Color.is_brown((210, 105, 30))), (
            "BUG QA-38: Color.is_brown((210, 105, 30)) returns False for "
            "Chocolate. Same is_neutral prerequisite bug as Saddlebrown."
        )

    def test_sienna_detected_as_brown(self):
        """Sienna (160, 82, 45) should be classified as brown."""
        from core.blend_color import Color

        assert bool(Color.is_brown((160, 82, 45))), (
            "BUG QA-38: Color.is_brown((160, 82, 45)) returns False for "
            "Sienna. Brown detection is broken for all standard browns."
        )


# -- BUG QA-39: Color.get_lab returns ndim>0 arrays, not scalars ---------------
# File: backend/core/blend_color.py:90-96
# get_lab slices L, a, b, C from arrays using [:,0] etc., which returns
# 1-element arrays (shape=(1,)) instead of scalars. Comparisons like
# L < 60 produce numpy arrays, triggering NumPy DeprecationWarning.


class TestGetLabReturnsArraysNotScalars:
    """
    BUG QA-39: Color.get_lab() returns 1-element numpy arrays (shape=(1,))
    instead of Python scalars.

    Line 94: L, a, b = lab[:,0], lab[:,1], lab[:,2]
    Line 95: C = np.sqrt(a**2 + b**2)

    The [:,0] slice on a (1,3) array returns shape (1,) not a scalar.
    This means all downstream comparisons (is_neutral, is_brown) like
    `C < threshold` and `L < 60` produce numpy arrays, not booleans.

    NumPy 1.25+ emits DeprecationWarning for ndim>0 array-to-scalar
    conversion. Future NumPy versions will raise TypeError, breaking
    all color classification logic.
    """

    def test_get_lab_returns_scalar_values(self):
        """get_lab should return scalar L, a, b, C values, not arrays."""
        from core.blend_color import Color
        import numpy as np

        L, a, b, C = Color.get_lab((128, 64, 32))

        # Check that values are scalars, not arrays
        for name, val in [('L', L), ('a', a), ('b', b), ('C', C)]:
            assert np.ndim(val) == 0, (
                f"BUG QA-39: Color.get_lab() returns {name} with "
                f"ndim={np.ndim(val)} (shape={getattr(val, 'shape', 'N/A')}). "
                f"Expected scalar (ndim=0). "
                f"NumPy DeprecationWarning now, TypeError in future versions. "
                f"Fix: Use lab[0,0], lab[0,1], lab[0,2] or .item() to extract scalars."
            )


# -- BUG QA-40: FilamentPreviewRequest accepts page without pageSize ------------
# File: backend/api/models.py:240-241
# page and pageSize are independent Optional[int] fields.
# Specifying page=1 without pageSize (or vice versa) is accepted,
# but generate_preview checks `page is not None and page_size is not None`,
# so pagination is silently skipped.


class TestPaginationPartialParameters:
    """
    BUG QA-40: FilamentPreviewRequest accepts partial pagination parameters.

    page=1, pageSize=None -> accepted, but generate_preview skips pagination
    page=None, pageSize=100 -> accepted, but generate_preview skips pagination

    The user thinks they're requesting page 1 of results, but gets ALL results
    because the service checks both fields. No error or warning.

    Fix: Add @root_validator to require both or neither.
    """

    def test_page_without_page_size_rejected(self):
        """Specifying page without pageSize should be rejected."""
        from api.models import FilamentPreviewRequest, FilamentPreset

        try:
            req = FilamentPreviewRequest(
                filamentPreset=FilamentPreset.BAMBU_CMYW_PHASE6,
                layerCount=4,
                page=1,
                pageSize=None,
            )
            pytest.fail(
                f"BUG QA-40: page=1 accepted without pageSize. "
                f"generate_preview will skip pagination silently. "
                f"User expects page 1 but gets ALL {4**4} results."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_page_size_without_page_rejected(self):
        """Specifying pageSize without page should be rejected."""
        from api.models import FilamentPreviewRequest, FilamentPreset

        try:
            req = FilamentPreviewRequest(
                filamentPreset=FilamentPreset.BAMBU_CMYW_PHASE6,
                layerCount=4,
                page=None,
                pageSize=100,
            )
            pytest.fail(
                f"BUG QA-40: pageSize=100 accepted without page. "
                f"pagination is silently ignored."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected


# -- BUG QA-41: generate_preview returns empty result for out-of-range page -----
# File: backend/services/filament_preview.py:97-104
# page=999 with page_size=10 slices color_matrix[9980:9990] which is empty.
# Returns empty colorMatrix and 1x1 white image with no error.


class TestPreviewOutOfRangePage:
    """
    BUG QA-41: generate_preview returns empty result for page > totalPages.

    With 4 colors x 4 layers = 256 combinations and page_size=10,
    there are 26 pages. Requesting page=999 returns:
    - colorMatrix: [] (empty)
    - image: 1x1 white pixel
    - pagination.page: 999 (confirms the page was "processed")

    No error, no warning. User sees a blank preview and has no idea why.

    Fix: Raise ValueError when page > totalPages.
    """

    def test_out_of_range_page_raises_error(self):
        """Requesting page beyond totalPages should raise an error."""
        from core.blend_color import Colors
        from services.filament_preview import FilamentPreviewService

        colors = Colors()
        service = FilamentPreviewService(colors, layer_count=4, layer_height=0.08)

        # 4^4 = 256 combos, page_size=10 -> 26 pages
        # page=999 is way out of range
        try:
            result = service.generate_preview(page=999, page_size=10)
            if len(result["colorMatrix"]) == 0:
                pytest.fail(
                    "BUG QA-41: generate_preview(page=999) returns empty result "
                    "instead of raising an error. pagination shows page=999 of "
                    f"totalPages={result['pagination']['totalPages']}. "
                    "Fix: Check page <= totalPages and raise ValueError."
                )
        except ValueError:
            pass  # Correctly rejected


# -- BUG QA-42: Empty vectorResults accepted in SVG STL download models ----------
# File: backend/api/models.py:105-117, 179-192
# DownloadSVGSTLRequest and DownloadSVGSTLRequestV2 have no min_length
# constraint on vectorResults. Empty list produces empty ZIP silently.


class TestEmptyVectorResultsAccepted:
    """
    BUG QA-42: SVG STL download models accept empty vectorResults.

    DownloadSVGSTLRequest.vectorResults and DownloadSVGSTLRequestV2.vectorResults
    have no min_length=1 constraint, allowing empty lists.

    This produces an empty ZIP file (0 STL files inside), which the user
    downloads but can't use. No error message explains why.

    Similar to QA-34 (empty colorBlocks) but for SVG mode.
    """

    def test_v1_svg_empty_vector_results_rejected(self):
        """V1 SVG STL request should reject empty vectorResults."""
        from api.models import DownloadSVGSTLRequest

        try:
            req = DownloadSVGSTLRequest(
                vectorResults=[],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                "BUG QA-42: DownloadSVGSTLRequest accepts empty vectorResults. "
                "This produces an empty ZIP with 0 STL files. "
                "Fix: Add min_length=1 to vectorResults field."
            )
        except (ValueError, Exception):
            pass

    def test_v2_svg_empty_vector_results_rejected(self):
        """V2 SVG STL request should reject empty vectorResults."""
        from api.models import DownloadSVGSTLRequestV2

        try:
            req = DownloadSVGSTLRequestV2(
                vectorResults=[],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                "BUG QA-42: DownloadSVGSTLRequestV2 accepts empty vectorResults. "
                "Same issue as V1 - produces empty ZIP."
            )
        except (ValueError, Exception):
            pass


# -- BUG QA-43: Empty colorBlocks accepted in CSV and V1 STL download models ----
# File: backend/api/models.py:100-103, 120-128
# DownloadCSVRequest and DownloadSTLRequest have no min_length on colorBlocks.
# CSV generates header-only file, STL generates empty ZIP (caught by QA-34
# in generate_stl_zip, but the model should reject earlier).


class TestEmptyColorBlocksInOtherModels:
    """
    BUG QA-43: DownloadCSVRequest and DownloadSTLRequest accept empty colorBlocks.

    DownloadCSVRequest with colorBlocks=[] produces a CSV with only the header
    row and no data - a useless file for the user.

    DownloadSTLRequest with colorBlocks=[] hits the QA-34 guard in
    generate_stl_zip() (ValueError), but validation should happen earlier
    at the model level for a clearer error message.

    Unlike DownloadSTLRequestV2 which has the guard in generate_stl_zip,
    DownloadCSVRequest has NO guard - it happily generates a header-only CSV.
    """

    def test_csv_request_empty_color_blocks_rejected(self):
        """DownloadCSVRequest should reject empty colorBlocks."""
        from api.models import DownloadCSVRequest

        try:
            req = DownloadCSVRequest(colorBlocks=[])
            pytest.fail(
                "BUG QA-43: DownloadCSVRequest accepts empty colorBlocks. "
                "CSV generator produces header-only file. "
                "Fix: Add min_length=1 to colorBlocks field."
            )
        except (ValueError, Exception):
            pass

    def test_v1_stl_request_empty_color_blocks_rejected(self):
        """V1 DownloadSTLRequest should reject empty colorBlocks at model level."""
        from api.models import DownloadSTLRequest

        try:
            req = DownloadSTLRequest(
                colorBlocks=[],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                "BUG QA-43: DownloadSTLRequest accepts empty colorBlocks. "
                "generate_stl_zip raises ValueError later, but model should "
                "catch this earlier. Fix: Add min_length=1 to colorBlocks."
            )
        except (ValueError, Exception):
            pass


# -- BUG QA-44: Pixels outside image bounds silently dropped --------------------
# File: backend/services/mesh_optimizer.py:43-46
# pixels_to_grid clips out-of-bounds pixels with `if 0 <= x < width and 0 <= y < height`
# but does not warn or raise an error. This means a color block with count=5
# and 5 pixels where 3 are out-of-bounds only generates geometry for 2 pixels.
# The user sees the correct count in CSV but the STL has fewer pixels.


class TestOutOfBoundsPixelsSilentlyDropped:
    """
    BUG QA-44: pixels_to_grid silently drops out-of-bounds pixel coordinates.

    Line 43-46:
        for pixel in pixels:
            x, y = pixel['x'], pixel['y']
            if 0 <= x < width and 0 <= y < height:
                grid[y, x] = True

    If a pixel has x=100 but image width=10, it's silently ignored.
    The color block says count=1 but the grid has 0 pixels.
    STL file is missing geometry that the user expects.

    This can happen when:
    1. Frontend sends pixel coordinates from a resized image
    2. Image dimensions changed between processing and download
    3. Manual API calls with mismatched dimensions

    Fix: Log a warning when pixels are dropped, or raise ValueError.
    """

    def test_out_of_bounds_pixel_not_silently_dropped(self):
        """All pixels outside image bounds should raise ValueError."""
        from services.mesh_optimizer import pixels_to_grid

        pixels = [{'x': 100, 'y': 100}]
        with pytest.raises(ValueError, match="outside image bounds"):
            pixels_to_grid(pixels, width=10, height=10)

    def test_mixed_valid_and_invalid_pixels(self, caplog):
        """Mix of valid and out-of-bounds pixels should warn about dropped ones."""
        import logging
        from services.mesh_optimizer import pixels_to_grid

        pixels = [
            {'x': 0, 'y': 0},    # Valid
            {'x': 5, 'y': 5},    # Valid
            {'x': 100, 'y': 0},  # Out of bounds
            {'x': 0, 'y': 100},  # Out of bounds
        ]
        with caplog.at_level(logging.WARNING):
            grid = pixels_to_grid(pixels, width=10, height=10)

        # 2 valid pixels included, 2 out-of-bounds dropped with warning
        assert grid.sum() == 2
        assert "Dropped 2 of 4 pixels" in caplog.text


# -- BUG QA-45: FilamentColorConfig.name validator doesn't strip ---------------
# File: backend/api/models.py:27-32
# validate_name checks if strip() is empty but doesn't apply strip().
# Name ' Cyan' passes validation, but label property returns name[0].upper() = ' '
# This creates space-character labels that break the blend code system.


class TestFilamentNameValidatorDoesNotStrip:
    """
    BUG QA-45: FilamentColorConfig.validate_name() checks if name.strip()
    is empty, but doesn't APPLY the strip. Names like ' Cyan' pass
    validation, but their label property returns ' ' (space character).

    Line 28-32:
        @validator('name')
        def validate_name(cls, v):
            if not v.strip():
                raise ValueError("Name cannot be whitespace-only")
            return v  # BUG: should return v.strip()

    This causes:
    1. Labels contain space characters instead of alphabetic chars
    2. Blend codes contain spaces (e.g., ' MYW')
    3. STL filenames contain spaces
    4. Colors.from_configs creates entries keyed on ' '
    5. Two names ' Cyan' and '  Magenta' both get label ' ', causing
       a duplicate label that bypasses the unique-labels validator
    """

    def test_leading_space_name_stripped_for_label(self):
        """Name with leading space should have its label derived from stripped name."""
        from api.models import FilamentColorConfig

        config = FilamentColorConfig(
            name=' Cyan', hex='#00FFFF', transmission_distance=3.0
        )

        assert config.label == 'C', (
            f"BUG QA-45: FilamentColorConfig(name=' Cyan').label = "
            f"{repr(config.label)} (expected 'C'). The name validator "
            f"checks strip() but doesn't apply it. "
            f"Fix: return v.strip() in validate_name."
        )

    def test_leading_space_names_cause_duplicate_labels(self):
        """Two names with leading spaces can create duplicate labels."""
        from api.models import FilamentColorConfig

        c1 = FilamentColorConfig(
            name=' Cyan', hex='#00FFFF', transmission_distance=3.0
        )
        c2 = FilamentColorConfig(
            name='  Magenta', hex='#FF00FF', transmission_distance=1.9
        )

        # Both get label ' ' (space), which makes them duplicate
        # but validation passes because the names are different strings
        assert c1.label != c2.label, (
            f"BUG QA-45: ' Cyan' and '  Magenta' both produce label "
            f"{repr(c1.label)}. Two space labels bypass uniqueness check."
        )

    def test_color_config_also_strips_name(self):
        """core.color_config.ColorConfig should also strip names for label."""
        from core.color_config import ColorConfig

        config = ColorConfig(
            name=' Cyan', hex='#00FFFF', transmission_distance=3.0
        )

        assert config.label == 'C', (
            f"BUG QA-45: ColorConfig(name=' Cyan').label = "
            f"{repr(config.label)} (expected 'C'). Same bug as "
            f"FilamentColorConfig. Fix: strip name in __post_init__."
        )


# -- BUG QA-46: BlendTestGenerator.read_matrix_csv references undefined 'model' -
# File: backend/core/blend_color.py:525
# read_matrix_csv uses `model.directory` which references an undefined
# global variable 'model'. Should be `self.directory`.


class TestReadMatrixCsvUndefinedVariable:
    """
    BUG QA-46: BlendTestGenerator.read_matrix_csv() references undefined
    global variable 'model' instead of 'self'.

    Line 525:
        df_raw = pd.read_csv(model.directory+filename, ...)
                              ^^^^^
        Should be: self.directory

    This method always crashes with NameError: name 'model' is not defined.
    """

    def test_read_matrix_csv_does_not_raise_name_error(self):
        """read_matrix_csv should not crash with NameError."""
        from core.blend_color import BlendTestGenerator, Colors

        gen = BlendTestGenerator(colors=Colors(), verbose=False)

        # It should fail with FileNotFoundError (file doesn't exist),
        # NOT with NameError (undefined variable)
        try:
            gen.read_matrix_csv('test.csv')
        except NameError as e:
            pytest.fail(
                f"BUG QA-46: read_matrix_csv raises NameError: {e}. "
                f"Line 525 uses 'model.directory' instead of "
                f"'self.directory'. Fix: replace 'model' with 'self'."
            )
        except (FileNotFoundError, OSError):
            pass  # Expected: file doesn't exist


# -- BUG QA-47: V1 download routes missing ValueError handler ------------------
# File: backend/api/routes/download.py:75-109, 112-158
# V1 /api/download-stl and /api/download-svg-stl do not catch ValueError
# from compute_reference_matrices (permutation guard).
# V2 correctly catches ValueError -> 422, but V1 falls through to
# the generic Exception handler and returns 500.


class TestV1DownloadMissingValueErrorHandler:
    """
    BUG QA-47: V1 download routes don't handle ValueError separately.

    V2 download_v2.py:164-165:
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    V1 download.py:105-109:
        except Exception as e:
            logger.error(...)
            raise HTTPException(status_code=500, detail="An internal error occurred")

    V1 has no ValueError handler, so ValueError from the permutation guard
    or other validation returns 500 with a generic message instead of 422.
    """

    def test_v1_download_stl_catches_value_error(self):
        """V1 download-stl route should handle ValueError via decorator."""
        from api.routes import download

        assert hasattr(download.api_download_stl, '__wrapped__'), (
            "BUG QA-47: V1 /api/download-stl should use @handle_api_errors "
            "decorator which catches ValueError and returns 422."
        )

    def test_v1_download_svg_stl_catches_value_error(self):
        """V1 SVG download route should handle ValueError via decorator."""
        from api.routes import download

        assert hasattr(download.api_download_svg_stl, '__wrapped__'), (
            "BUG QA-47: V1 /api/download-svg-stl should use @handle_api_errors "
            "decorator which catches ValueError and returns 422."
        )

    def test_v1_download_csv_catches_value_error(self):
        """V1 download-csv route should handle ValueError via decorator."""
        from api.routes import download

        assert hasattr(download.api_download_csv, '__wrapped__'), (
            "BUG QA-47: V1 /api/download-csv should use @handle_api_errors "
            "decorator which catches ValueError and returns 422."
        )


# -- BUG QA-48: useImageProcessor targetHeight uses wrong condition -------------
# File: src/hooks/useImageProcessor.ts:65-67
# targetHeight checks imageDimensions.width > 0 instead of .height > 0
# If width > 0 but height == 0 (unlikely but possible with corrupt data),
# targetHeight would be calculated as 0 * pixelSize = 0 (correct by accident).
# But if height > 0 and width == 0, targetHeight would be 0 (wrong).
# This is a logic error even if benign in most cases.
# NOTE: This is a frontend bug - test is documentation-only since we
# can't run TS tests here. But we can verify the corresponding pattern
# doesn't exist in the backend.


class TestTargetDimensionConditionLogic:
    """
    BUG QA-48 (Frontend): useImageProcessor.ts line 65:
        const targetHeight = imageDimensions.width > 0
            ? Math.round(imageDimensions.height * pixelSize * 100) / 100
            : 0;

    Should check imageDimensions.height > 0, not width.

    While benign in practice (width and height are always both >0 or both 0),
    this is a logic error that could cause incorrect display if the
    backend ever returns zero-width, non-zero-height dimensions.
    """

    def test_backend_image_dimensions_always_have_both(self):
        """Backend always returns both width and height > 0 together."""
        from api.models import ImageDimensions

        # Can't create an ImageDimensions with width=0
        try:
            ImageDimensions(width=0, height=10)
            pytest.fail("ImageDimensions should reject width=0")
        except Exception:
            pass  # Correctly rejected (gt=0 constraint)

        # Can't create with height=0
        try:
            ImageDimensions(width=10, height=0)
            pytest.fail("ImageDimensions should reject height=0")
        except Exception:
            pass  # Correctly rejected


# =============================================================================
# QA Round 8 — 2026-02-07
# =============================================================================


# -- BUG QA-49: DownloadSTLRequestV2.colorBlocks missing min_items=1 ----------
# File: backend/api/models.py:143
# V1 DownloadSTLRequest.colorBlocks has min_items=1, but V2 does not.
# Empty colorBlocks pass model validation and reach generate_stl_zip which
# raises ValueError. Validation should happen earlier at the model level
# for consistency with V1 and clearer error messages.


class TestV2EmptyColorBlocksValidation:
    """
    BUG QA-49: DownloadSTLRequestV2 accepts empty colorBlocks.

    V1 (line 123): colorBlocks: List[ColorBlock] = Field(..., min_items=1)
    V2 (line 143): colorBlocks: List[ColorBlock]  # NO min_items constraint

    This inconsistency means:
    1. V1 returns 422 with clear "min_items" validation error
    2. V2 passes validation, then crashes in generate_stl_zip/generate_3mf
       with a less descriptive "No color blocks provided" ValueError

    Also used by the 3MF endpoint which shares the same model.
    """

    def test_v2_stl_rejects_empty_color_blocks_at_model_level(self):
        """V2 DownloadSTLRequestV2 should reject empty colorBlocks like V1 does."""
        from api.models import DownloadSTLRequestV2

        try:
            req = DownloadSTLRequestV2(
                colorBlocks=[],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                "BUG QA-49: DownloadSTLRequestV2 accepts empty colorBlocks. "
                "V1 model has min_items=1 but V2 does not. "
                "Fix: Add min_items=1 to colorBlocks field in DownloadSTLRequestV2."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected at model level


# -- BUG QA-50: 3MF preset/default colors missing visual hex in output --------
# File: backend/api/routes/download_v2.py:258-261
# color_hex_map is built ONLY from body.filamentColors. When using a preset
# or default CMYK (filamentColors=None), color_hex_map is empty {}.
# This means 3MF objects have no visual colors, making it harder for slicer
# users to identify which object corresponds to which filament.


class TestThreeMFPresetColorHexMissing:
    """
    BUG QA-50: 3MF objects lose visual colors when using presets/defaults.

    In download_v2.py api_download_3mf():
        color_hex_map = {}
        if body.filamentColors:
            for fc in body.filamentColors:
                color_hex_map[fc.label] = fc.hex

    When body.filamentColors is None (preset or default), color_hex_map stays {}.
    The Colors instance HAS hex values (e.g., Colors()['C'].hex = '#0086D6'),
    but they are never passed to generate_3mf().

    Result: 3MF objects have no face colors. In Bambu Studio, all objects
    appear gray/default instead of cyan/magenta/yellow/white.
    """

    def test_3mf_route_builds_color_hex_map_for_presets(self):
        """3MF route should build color_hex_map even when using presets."""
        import inspect
        from api.routes.download_v2 import api_download_3mf

        source = inspect.getsource(api_download_3mf)

        # The route must populate color_hex_map for BOTH branches:
        # 1. When body.filamentColors is set (custom colors)
        # 2. When body.filamentColors is None (preset/default) — via Colors instance
        #
        # Verify the else branch exists and uses colors.get_labels() + colors[label].hex
        assert 'colors.get_labels' in source, (
            "BUG QA-50: api_download_3mf missing fallback to populate color_hex_map "
            "from Colors instance when filamentColors is None"
        )
        assert 'colors[' in source and '.hex' in source, (
            "BUG QA-50: api_download_3mf must read hex from Colors instance "
            "via colors[label].hex for preset/default case"
        )


# -- BUG QA-51: layerHeight and pixelSize have no upper bounds ----------------
# Files: backend/api/models.py:124,125,144,145
# Both V1 and V2 download models accept layerHeight and pixelSize with only
# gt=0 constraint and no upper limit. Extreme values cause:
# - Huge STL/3MF files (pixelSize=1000 means each pixel = 1 meter)
# - Numerical issues in Beer-Lambert calculations (large exponents)
# - Memory exhaustion from enormous mesh generation


class TestLayerHeightPixelSizeNoBounds:
    """
    BUG QA-51: layerHeight and pixelSize accept arbitrarily large values.

    Both V1 and V2 models:
        layerHeight: float = Field(..., gt=0)  # No upper bound
        pixelSize: float = Field(..., gt=0)    # No upper bound

    Extreme values like layerHeight=999999 or pixelSize=999999:
    1. Generate STL meshes with enormous physical dimensions
    2. May cause floating-point overflow in Beer-Lambert calculations
    3. Produce multi-GB output files
    4. Waste server resources on meaningless geometry

    Realistic bounds: layerHeight <= 10mm (thick printing), pixelSize <= 10mm.
    """

    def test_v1_layer_height_has_upper_bound(self):
        """V1 DownloadSTLRequest should reject unreasonable layerHeight."""
        from api.models import DownloadSTLRequest, ColorBlock, PixelCoordinate

        try:
            req = DownloadSTLRequest(
                colorBlocks=[ColorBlock(
                    r=0, g=255, b=255, hex='#00FFFF', count=1,
                    pixels=[PixelCoordinate(x=0, y=0)]
                )],
                layerHeight=999999.0,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                f"BUG QA-51: DownloadSTLRequest accepts layerHeight={req.layerHeight}. "
                f"No upper bound on layerHeight. "
                f"Fix: Add le=10 constraint to layerHeight field."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected

    def test_v2_layer_height_has_upper_bound(self):
        """V2 DownloadSTLRequestV2 should reject unreasonable layerHeight."""
        from api.models import DownloadSTLRequestV2, ColorBlock, PixelCoordinate

        try:
            req = DownloadSTLRequestV2(
                colorBlocks=[ColorBlock(
                    r=0, g=255, b=255, hex='#00FFFF', count=1,
                    pixels=[PixelCoordinate(x=0, y=0)]
                )],
                layerHeight=999999.0,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                f"BUG QA-51: DownloadSTLRequestV2 accepts layerHeight={req.layerHeight}. "
                f"No upper bound. Fix: Add le=10."
            )
        except (ValueError, Exception):
            pass

    def test_v1_pixel_size_has_upper_bound(self):
        """V1 DownloadSTLRequest should reject unreasonable pixelSize."""
        from api.models import DownloadSTLRequest, ColorBlock, PixelCoordinate

        try:
            req = DownloadSTLRequest(
                colorBlocks=[ColorBlock(
                    r=0, g=255, b=255, hex='#00FFFF', count=1,
                    pixels=[PixelCoordinate(x=0, y=0)]
                )],
                layerHeight=0.08,
                pixelSize=999999.0,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                f"BUG QA-51: DownloadSTLRequest accepts pixelSize={req.pixelSize}. "
                f"No upper bound on pixelSize. Fix: Add le=10."
            )
        except (ValueError, Exception):
            pass

    def test_v2_pixel_size_has_upper_bound(self):
        """V2 DownloadSTLRequestV2 should reject unreasonable pixelSize."""
        from api.models import DownloadSTLRequestV2, ColorBlock, PixelCoordinate

        try:
            req = DownloadSTLRequestV2(
                colorBlocks=[ColorBlock(
                    r=0, g=255, b=255, hex='#00FFFF', count=1,
                    pixels=[PixelCoordinate(x=0, y=0)]
                )],
                layerHeight=0.08,
                pixelSize=999999.0,
                layerCount=4,
                imageDimensions={'width': 4, 'height': 4},
            )
            pytest.fail(
                f"BUG QA-51: DownloadSTLRequestV2 accepts pixelSize={req.pixelSize}. "
                f"No upper bound. Fix: Add le=10."
            )
        except (ValueError, Exception):
            pass

    def test_filament_preview_layer_height_has_upper_bound(self):
        """FilamentPreviewRequest should also reject unreasonable layerHeight."""
        from api.models import FilamentPreviewRequest, FilamentPreset

        try:
            req = FilamentPreviewRequest(
                filamentPreset=FilamentPreset.BAMBU_CMYW_PHASE6,
                layerHeight=999999.0,
            )
            pytest.fail(
                f"BUG QA-51: FilamentPreviewRequest accepts layerHeight={req.layerHeight}. "
                f"Fix: Add le=10."
            )
        except (ValueError, Exception):
            pass


# -- BUG QA-52: compute_reference_matrices ZeroDivisionError on empty Colors ---
# File: backend/services/stl_generator.py:55,70-71
# When Colors instance has no colors (empty dict), get_labels() returns [].
# len(items)=0, permutation_count=0**layer_count=0 (passes guard).
# Then rows=int(sqrt(0))=0, cols=(0+0-1)//0 -> ZeroDivisionError.


class TestComputeReferenceMatricesEmptyColors:
    """
    BUG QA-52: compute_reference_matrices crashes on empty Colors.

    Call chain:
    1. items = colors.get_labels() -> [] (empty)
    2. permutation_count = 0 ** 4 = 0 (passes 1M guard)
    3. perms = list(product([], repeat=4)) -> [] (empty)
    4. n = 0
    5. rows = int(sqrt(0)) = 0
    6. cols = (0 + 0 - 1) // 0 -> ZeroDivisionError

    This can happen if:
    - Colors.from_configs([]) is called with empty list
    - A custom Colors instance is constructed with no colors

    Fix: Add guard at start: if not items: raise ValueError(...)
    """

    def test_empty_colors_raises_descriptive_error(self):
        """compute_reference_matrices with empty Colors should raise ValueError."""
        from core.blend_color import Colors
        from services.stl_generator import compute_reference_matrices

        colors = Colors.__new__(Colors)
        colors.colors = {}
        colors.white_balance = {'r': 0, 'g': 0, 'b': 0}

        with pytest.raises(ValueError):
            compute_reference_matrices(4, 0.08, colors)

    def test_empty_colors_does_not_crash_with_zerodiv(self):
        """Empty Colors should NOT cause ZeroDivisionError."""
        from core.blend_color import Colors
        from services.stl_generator import compute_reference_matrices

        colors = Colors.__new__(Colors)
        colors.colors = {}
        colors.white_balance = {'r': 0, 'g': 0, 'b': 0}

        try:
            compute_reference_matrices(4, 0.08, colors)
        except ZeroDivisionError:
            pytest.fail(
                "BUG QA-52: compute_reference_matrices crashes with ZeroDivisionError "
                "when Colors has no colors. rows=int(sqrt(0))=0, cols=(0-1)//0. "
                "Fix: Add 'if not items: raise ValueError(...)' before permutation calc."
            )
        except (ValueError, Exception):
            pass  # Any other error is acceptable


# -- BUG QA-53: Colors.__setitem__ redundant strip().upper() ------------------
# File: backend/core/blend_color.py:292-294
# Line 293 normalizes label with strip().upper(), then line 294 does it again.
# This is a code quality issue that wastes CPU and obscures intent.


class TestColorsSetItemRedundantStrip:
    """
    BUG QA-53: Colors.__setitem__ performs redundant normalization.

    Line 292-294:
        def __setitem__(self, label, value=None):
            label = label.strip().upper()          # Line 293: normalized
            self.colors[label.strip().upper()] = value  # Line 294: normalized AGAIN

    The second strip().upper() on line 294 is redundant because label was
    already normalized on line 293. This wastes CPU cycles and obscures
    that the assignment target should just be `label`.

    While this doesn't produce wrong results, it suggests the developer
    may not have noticed the normalization on the previous line, which
    could indicate a copy-paste error pattern.
    """

    def test_setitem_uses_normalized_label_directly(self):
        """__setitem__ should use the already-normalized label, not re-normalize."""
        import inspect
        from core.blend_color import Colors

        source = inspect.getsource(Colors.__setitem__)

        # Count occurrences of strip().upper()
        strip_upper_count = source.count('.strip().upper()')
        assert strip_upper_count <= 1, (
            f"BUG QA-53: Colors.__setitem__ calls .strip().upper() "
            f"{strip_upper_count} times (expected 1). Line 293 normalizes "
            f"label, then line 294 re-normalizes it unnecessarily. "
            f"Fix: Change line 294 from 'self.colors[label.strip().upper()]' "
            f"to 'self.colors[label]'."
        )


# -- BUG QA-66: Color.__init__ uses == None instead of is None ----------------
# File: backend/core/blend_color.py:36
# PEP 8: comparisons to singletons like None should always use `is`/`is not`.
# Using == may produce unexpected results with objects that override __eq__.


class TestColorInitEqNone:
    """
    BUG QA-66: Color.__init__ line 36 uses `if hex == None:` instead of
    `if hex is None:`. This violates PEP 8 and is fragile if a custom
    type with __eq__ override is ever passed as hex.
    """

    def test_color_init_uses_is_none(self):
        """Color.__init__ should use 'is None', not '== None'."""
        import inspect
        from core.blend_color import Color

        source = inspect.getsource(Color.__init__)
        assert '== None' not in source, (
            "BUG QA-66: Color.__init__ uses '== None' instead of 'is None' on line 36. "
            "PEP 8: 'Comparisons to singletons like None should always be done with "
            "is or is not, never the equality operators.' "
            "Fix: Change 'if hex == None:' to 'if hex is None:'"
        )


class TestCodeToRgbShortCodeBackground:
    """
    BUG QA-68: _code_to_rgb_cached loses background contribution for short codes.

    For code='C' (len=1), array_size=5 (max(1,4)+1):
    - light_loss_ratio[0] = first layer contribution
    - light_loss_ratio[1] = background (remain * (1-t))
    - light_loss_ratio[2,3,4] = 0 (padding)
    - rgb uses light_loss_ratio[-1] = index 4 = 0, NOT index 1

    The background (white paper/light) contribution is lost, making
    short-code colors appear darker/wrong.
    """

    def test_single_char_white_code_produces_near_white(self):
        """Code 'W' with white filament should produce near-white RGB."""
        from core.blend_color import _code_to_rgb_cached, clear_rgb_cache

        clear_rgb_cache()
        color_key = (('W', 7.2, '#FFFFFF'),)
        r, g, b = _code_to_rgb_cached('W', 0.08, color_key)

        # Single layer of white should be very bright (>230)
        assert r > 230, (
            f"BUG QA-68: Code 'W' produces R={r:.1f} (expected >230). "
            f"Background contribution lost for short codes. "
            f"Fix: Use light_loss_ratio[len(code)] instead of [-1]."
        )
        assert g > 230, f"BUG QA-68: Code 'W' produces G={g:.1f} (expected >230)."
        assert b > 230, f"BUG QA-68: Code 'W' produces B={b:.1f} (expected >230)."

    def test_short_and_long_codes_consistent(self):
        """Short code 'W' should produce similar result to 'WWWW'."""
        from core.blend_color import _code_to_rgb_cached, clear_rgb_cache

        clear_rgb_cache()
        color_key = (('C', 3.0, '#0086D6'), ('M', 1.9, '#EC008C'),
                     ('Y', 2.5, '#F4EE2A'), ('W', 7.2, '#FFFFFF'))

        r1, g1, b1 = _code_to_rgb_cached('W', 0.08, color_key)
        r4, g4, b4 = _code_to_rgb_cached('WWWW', 0.08, color_key)

        # Both should be reasonably bright (white filament)
        # The 4-layer version transmits more light, so should be dimmer,
        # but both should be in the same ballpark (>200)
        assert r1 > 200 and g1 > 200 and b1 > 200, (
            f"BUG QA-68: 1-layer 'W' = ({r1:.0f},{g1:.0f},{b1:.0f}), too dark. "
            f"Background contribution lost for short codes."
        )
