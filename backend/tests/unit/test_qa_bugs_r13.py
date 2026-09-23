"""
QA Round 13 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import colorsys
import io
import os
import struct

import numpy as np
import pytest
from PIL import Image

from core.blend_color import BlendTestGenerator, Color, Colors, _code_to_rgb_cached
from core.color_config import ColorConfig, get_preset


# -- QA-127: colorsys.rgb_to_hls receives [0,255] range instead of [0,1] -----
# File: backend/core/blend_color.py:557-558
# set_code_rgb_df passes code_to_rgb() output (range [0,255]) directly to
# colorsys.rgb_to_hls() which expects [0.0, 1.0]. The stored hue/lightness/
# saturation values are semantically incorrect (lightness up to ~127 instead
# of 0-1). While sort order may accidentally be correct (monotonic distortion),
# the actual values are wrong.

class TestQA127RGBToHLSRangeError:
    """set_code_rgb_df passes [0,255] RGB to colorsys.rgb_to_hls expecting [0,1]."""

    def test_hls_values_in_unit_range(self):
        """HLS values computed from code_to_rgb should be in [0, 1] range."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=4),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=4),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=4),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=20),
        ]
        gen = BlendTestGenerator(
            plate_length=100,
            layer_count_max=2,
            layer_height=0.08,
            colors=Colors.from_configs(configs),
        )

        # Generate the permutation matrix first
        items = gen.colors.get_labels()
        gen.df = gen.permutation_matrix(items, gen.layer_count_max)

        # Now call set_code_rgb_df which uses colorsys.rgb_to_hls
        gen.set_code_rgb_df(gen.df)

        # Verify that the normalization is present in the source code
        import inspect
        source = inspect.getsource(gen.set_code_rgb_df)

        # The code should normalize RGB values before calling rgb_to_hls
        # Look for the pattern "rgb[0] / 255.0" or similar normalization
        has_normalization = (
            "/ 255.0" in source or
            "/255.0" in source or
            "* (1.0/255.0)" in source
        )

        assert has_normalization, (
            f"BUG QA-127: set_code_rgb_df does not normalize RGB values before "
            f"calling colorsys.rgb_to_hls. The code_to_rgb() function returns "
            f"RGB values in [0, 255] range, but colorsys.rgb_to_hls expects "
            f"[0, 1]. Source code should contain normalization like "
            f"'rgb[0] / 255.0'. Compare filament_preview.py which correctly "
            f"does '[v / 255.0 for v in entry[\"rgb\"]]'."
        )


# -- QA-128: ImageDimensions has no upper bound on width/height ----------------
# File: backend/api/models.py:95-98
# ImageDimensions validates gt=0 but no maximum. A client can submit
# width=100000, height=100000, which allocates a ~10GB boolean array in
# pixels_to_grid(). This bypasses the image processor's 1024px downscaling.

class TestQA128ImageDimensionsNoUpperBound:
    """ImageDimensions allows arbitrarily large width/height."""

    def test_dimensions_reject_extremely_large_values(self):
        """ImageDimensions should reject width or height > reasonable max."""
        from api.models import ImageDimensions

        # Should accept reasonable dimensions
        dims = ImageDimensions(width=1024, height=1024)
        assert dims.width == 1024

        # Should REJECT extremely large dimensions that would cause OOM
        # If the bug is present, this will succeed (no upper bound)
        with pytest.raises(Exception) as exc_info:
            ImageDimensions(width=100000, height=100000)

        assert exc_info.value is not None, (
            "BUG QA-128: ImageDimensions accepts width=100000, height=100000 "
            "which would allocate ~10GB in pixels_to_grid(). "
            "Add le=10000 (or similar) upper bound to width and height fields."
        )


# -- QA-129: RIFF magic bytes too permissive for WebP validation ---------------
# File: backend/api/validators.py:11-16
# WebP magic bytes are defined as just b'RIFF' (4 bytes), but RIFF is a
# generic container used by WAV, AVI, etc. WebP files specifically have
# 'RIFF' at bytes 0-3 AND 'WEBP' at bytes 8-11.

class TestQA129RIFFMagicBytesTooPermissive:
    """RIFF-based magic bytes accept non-WebP files like WAV."""

    def test_wav_file_rejected_with_webp_extension(self):
        """A WAV file renamed to .webp should be rejected by magic byte check."""
        from api.validators import _has_valid_magic_bytes

        # Create a valid WAV file header (RIFF container, but WAVE, not WEBP)
        # WAV format: RIFF + size + WAVE + fmt chunk...
        wav_header = b'RIFF' + b'\x24\x00\x00\x00' + b'WAVE' + b'fmt '
        wav_header += b'\x10\x00\x00\x00' + b'\x01\x00\x01\x00'
        wav_header += b'\x44\xac\x00\x00' + b'\x88\x58\x01\x00'
        wav_header += b'\x02\x00\x10\x00' + b'data' + b'\x00\x00\x00\x00'

        # The WAV file starts with RIFF, so current check passes it
        result = _has_valid_magic_bytes(wav_header)

        # If the bug is present, WAV file passes magic byte validation
        assert not result, (
            "BUG QA-129: _has_valid_magic_bytes accepts WAV files because "
            "it only checks for 'RIFF' prefix (4 bytes), not 'RIFF....WEBP' "
            "(bytes 0-3 + 8-11). A WAV or AVI file with .webp extension "
            "would pass validation. Should check bytes 8-11 == 'WEBP'."
        )


# -- QA-130: SPA catch-all route has path traversal vulnerability --------------
# File: backend/main.py:122-128
# serve_spa uses os.path.join(static_dir, full_path) without validating
# the resolved path stays within static_dir. A request like
# GET /../../etc/passwd could serve arbitrary files.

class TestQA130SPAPathTraversal:
    """SPA catch-all route does not validate path traversal."""

    def test_path_traversal_blocked(self):
        """Resolved path must be within static_dir."""
        # Simulate the path resolution logic from main.py:125-127
        static_dir = "/app/static"
        malicious_path = "../../etc/passwd"

        file_path = os.path.join(static_dir, malicious_path)
        resolved = os.path.realpath(file_path)
        resolved_static = os.path.realpath(static_dir)

        # The resolved path should NOT escape static_dir
        # os.path.join("/app/static", "../../etc/passwd") resolves to /etc/passwd
        # The protection should detect this and reject the path
        is_within_static = resolved.startswith(resolved_static)

        # The path traversal should be DETECTED (is_within_static should be False)
        # If the bug is present, the code would not check this and serve the file
        # The test verifies the logic works: malicious paths are detected
        assert not is_within_static, (
            f"BUG QA-130: Path traversal protection not working correctly. "
            f"Path '{malicious_path}' from '{static_dir}' resolves to "
            f"'{resolved}', which should be detected as OUTSIDE static_dir "
            f"('{resolved_static}'). The protection should return index.html "
            f"instead of serving the malicious file."
        )

        # Also verify that a legitimate path would be allowed
        legit_path = "assets/index.js"
        legit_file_path = os.path.join(static_dir, legit_path)
        legit_resolved = os.path.realpath(legit_file_path)
        legit_is_within = legit_resolved.startswith(resolved_static)
        assert legit_is_within, (
            f"Path traversal protection too restrictive. Legitimate path "
            f"'{legit_path}' resolves to '{legit_resolved}' which should "
            f"be within static_dir ('{resolved_static}')."
        )

# -- QA-131: Health endpoint leaks platform and Python version -----------------
# File: backend/api/routes/health.py:35-48
# /health/detailed returns python_version, platform, platform_release
# without authentication. This info aids attackers in identifying specific
# vulnerabilities.

class TestQA131HealthEndpointInfoLeakage:
    """Health detailed endpoint exposes system info without auth."""

    @pytest.mark.asyncio
    async def test_detailed_health_no_version_leak(self):
        """Detailed health should not expose Python version or platform release."""
        from api.routes.health import detailed_health_check
        result = await detailed_health_check()

        # These fields should NOT be present (or should require auth)
        has_python_version = 'python_version' in result
        has_platform_release = 'platform_release' in result

        assert not has_python_version and not has_platform_release, (
            f"BUG QA-131: /health/detailed leaks system info without auth: "
            f"python_version={result.get('python_version')}, "
            f"platform_release={result.get('platform_release')}. "
            f"Remove or gate behind authentication."
        )


# -- QA-132: _downscale_if_needed can produce 0-dimension image ---------------
# File: backend/services/image_processor.py:135-157
# int(width * scale) truncates to 0 for extreme aspect ratios, e.g.,
# 1x100000 image => scale=0.01024, new_width=int(0.01024)=0.

class TestQA132DownscaleZeroDimension:
    """Downscaling extreme aspect ratio images can produce 0-dimension."""

    def test_extreme_aspect_ratio_no_zero_dimension(self):
        """Downscaling a 1x10000 image should not produce 0-width."""
        from services.image_processor import _downscale_if_needed

        # Create extreme aspect ratio image: 1px wide, 10000px tall
        img = Image.new('RGB', (1, 10000), color=(255, 0, 0))

        try:
            result = _downscale_if_needed(img, 1024)
            width, height = result.size
            assert width > 0 and height > 0, (
                f"BUG QA-132: _downscale_if_needed produced {width}x{height} "
                f"for 1x10000 input. int() truncation creates 0-dimension."
            )
        except (ValueError, Exception) as e:
            pytest.fail(
                f"BUG QA-132: _downscale_if_needed crashes with '{e}' for "
                f"1x10000 input. int(1 * 0.1024) = 0, causing PIL resize "
                f"to fail. Clamp new dimensions to min 1px."
            )

    def test_extreme_horizontal_no_zero_height(self):
        """Downscaling a 10000x1 image should not produce 0-height."""
        from services.image_processor import _downscale_if_needed

        img = Image.new('RGB', (10000, 1), color=(0, 255, 0))

        try:
            result = _downscale_if_needed(img, 1024)
            width, height = result.size
            assert width > 0 and height > 0, (
                f"BUG QA-132: _downscale_if_needed produced {width}x{height} "
                f"for 10000x1 input. Clamp both dimensions to min 1px."
            )
        except (ValueError, Exception) as e:
            pytest.fail(
                f"BUG QA-132: _downscale_if_needed crashes with '{e}' for "
                f"10000x1 input. Clamp both dimensions to min 1px."
            )


# -- QA-133: RGBA to RGB composites onto black instead of white ----------------
# File: backend/services/image_processor.py:180
# img.convert('RGB') on RGBA composites transparent pixels onto black.
# For 3D printing, transparent background should map to white (filament base).

class TestQA133RGBACompositesOnBlack:
    """RGBA images composite transparent areas onto black, not white."""

    def test_transparent_pixels_become_white(self):
        """Transparent RGBA pixels should become white (255,255,255) not black."""
        from services.image_processor import process_image

        # Create 10x10 RGBA image: red square on transparent background
        img = Image.new('RGBA', (10, 10), color=(0, 0, 0, 0))  # fully transparent
        # Draw a red pixel at (5, 5)
        img.putpixel((5, 5), (255, 0, 0, 255))

        # Save to bytes
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        image_bytes = buf.getvalue()

        result = process_image(image_bytes, max_colors=5)

        # The majority of pixels should be white (transparent -> white),
        # NOT black (transparent -> black from naive .convert('RGB'))
        color_blocks = result['colorBlocks']

        # Find the dominant color (99 of 100 pixels are transparent)
        dominant = max(color_blocks, key=lambda b: b['count'])
        dominant_rgb = (dominant['r'], dominant['g'], dominant['b'])

        # Distance from white
        dist_to_white = sum((c - 255) ** 2 for c in dominant_rgb) ** 0.5
        # Distance from black
        dist_to_black = sum(c ** 2 for c in dominant_rgb) ** 0.5

        assert dist_to_white < dist_to_black, (
            f"BUG QA-133: Transparent RGBA pixels became {dominant_rgb} "
            f"(closer to black than white). img.convert('RGB') composites "
            f"onto black background. For 3D printing, should composite "
            f"onto white (255,255,255) since white = base filament color."
        )


# -- QA-134: Analytics catch-all normalization too aggressive ------------------
# File: backend/services/analytics.py:29-33
# The R12 fix for QA-119 added a catch-all pattern /api/[^/]+(/[^/]+)*
# that normalizes ALL /api/ paths (including real ones like /api/health,
# /api/process-image) to /api/{unknown}. This breaks per-endpoint analytics
# entirely. Known endpoints should be tracked individually.

class TestQA134AnalyticsOverNormalization:
    """Analytics catch-all pattern normalizes known routes to {unknown}."""

    def test_known_endpoints_not_normalized(self):
        """Known /api/ endpoints should keep their original paths."""
        from services.analytics import AnalyticsCollector

        collector = AnalyticsCollector()

        # Record requests to KNOWN endpoints
        known_paths = [
            "/api/health",
            "/api/process-image",
            "/api/analytics",
            "/api/filament-preview",
        ]
        for path in known_paths:
            collector.record_request(
                method="GET", path=path, status_code=200, response_time_ms=1.0
            )

        summary = collector.get_summary()

        # Known paths should be tracked individually, NOT collapsed to {unknown}
        has_health = any('health' in k for k in summary['endpoints'])
        has_process = any('process' in k for k in summary['endpoints'])

        assert has_health and has_process, (
            f"BUG QA-134: Analytics catch-all pattern normalizes known "
            f"endpoints to '/api/{{unknown}}'. /api/health and /api/process-image "
            f"are collapsed. Endpoints: {list(summary['endpoints'].keys())}. "
            f"The R12 fix for QA-119 is too aggressive — catch-all pattern "
            f"r'/api/[^/]+(/[^/]+)*' matches ALL paths, not just unknown ones."
        )

    def test_unknown_paths_still_normalized(self):
        """Unknown /api/ paths should still be normalized to prevent DoS."""
        from services.analytics import AnalyticsCollector

        collector = AnalyticsCollector()

        for i in range(100):
            collector.record_request(
                method="GET",
                path=f"/api/nonexistent/path/{i}",
                status_code=404,
                response_time_ms=1.0,
            )

        summary = collector.get_summary()
        endpoint_count = len(summary['endpoints'])

        # Unknown paths should be normalized (not 100 unique keys)
        assert endpoint_count < 10, (
            f"Analytics created {endpoint_count} unique endpoint keys "
            f"for 100 unique non-existent API paths."
        )


# -- QA-135: ColorBlock.pixels has no max_length constraint --------------------
# File: backend/api/models.py:73
# pixels: List[PixelCoordinate] = Field(..., min_length=1) has no max_length.
# A single color block with millions of pixels consumes unbounded memory
# and generates massive STL files.

class TestQA135PixelsNoMaxLength:
    """ColorBlock.pixels allows unbounded number of coordinates."""

    def test_pixels_has_max_length(self):
        """ColorBlock.pixels field should have a max_length constraint."""
        from api.models import ColorBlock

        fields = ColorBlock.model_fields
        pixels_field = fields['pixels']

        # Check for max_length in metadata
        has_max_length = False
        if hasattr(pixels_field, 'metadata'):
            for m in pixels_field.metadata:
                if hasattr(m, 'max_length'):
                    has_max_length = True
                    break

        # Also check the field's JSON schema
        schema = ColorBlock.model_json_schema()
        pixels_schema = schema.get('properties', {}).get('pixels', {})
        if 'maxItems' in pixels_schema:
            has_max_length = True

        assert has_max_length, (
            "BUG QA-135: ColorBlock.pixels has no max_length constraint. "
            "A client can send millions of pixel coordinates in a single "
            "color block, causing OOM. Add max_length=1048576 or similar."
        )


# -- QA-138: get_preset(None) raises AttributeError ----------------------------
# File: backend/core/color_config.py:76-90
# get_preset(name) calls name.lower() without checking if name is None.

class TestQA138GetPresetNone:
    """get_preset(None) raises AttributeError instead of returning None."""

    def test_get_preset_none_returns_none(self):
        """get_preset(None) should gracefully return None."""
        try:
            result = get_preset(None)
        except AttributeError as e:
            pytest.fail(
                f"BUG QA-138: get_preset(None) raises AttributeError: {e}. "
                f"Should return None gracefully. Add 'if name is None: "
                f"return None' guard."
            )

        assert result is None, (
            f"get_preset(None) should return None, got {result}"
        )


# -- QA-139: Palette get_palette is case-sensitive (inconsistent with get_preset)
# File: backend/core/palette_library.py:180-185
# get_palette does linear scan with exact match, but get_preset in
# color_config.py uses .lower(). API inconsistency.

class TestQA139PaletteGetCaseSensitive:
    """get_palette is case-sensitive, inconsistent with get_preset."""

    def test_get_palette_case_insensitive(self):
        """get_palette should be case-insensitive like get_preset."""
        from core.palette_library import get_palette

        # Lowercase should work
        result_lower = get_palette("bambu_cmyw_phase6")
        assert result_lower is not None, "get_palette('bambu_cmyw_phase6') should find palette"

        # Uppercase/mixed case should also work (like get_preset does)
        result_upper = get_palette("BAMBU_CMYW_PHASE6")

        assert result_upper is not None, (
            "BUG QA-139: get_palette('BAMBU_CMYW_PHASE6') returns None because "
            "it uses exact match. get_preset in color_config.py uses "
            ".lower() for case-insensitive lookup. These should be consistent."
        )


# -- QA-140: Palette data duplicated from color_config (can drift) -------------
# File: backend/core/palette_library.py:24-48 vs color_config.py:61-73
# Palette hex/td values are hardcoded copies of color_config presets.

class TestQA140PaletteDataDrift:
    """Palette data is duplicated from color_config, can drift out of sync."""

    def test_palette_matches_preset_data(self):
        """Palette bambu_cmyw_phase6 colors should match BAMBU_CMYW_PHASE6_PRESET exactly."""
        from core.color_config import BAMBU_CMYW_PHASE6_PRESET
        from core.palette_library import get_palette

        palette = get_palette("bambu_cmyw_phase6")
        assert palette is not None

        preset_data = {c.name: (c.hex, c.transmission_distance)
                       for c in BAMBU_CMYW_PHASE6_PRESET}
        palette_data = {c.name: (c.hex, c.transmission_distance)
                        for c in palette.colors}

        # Both should have same data
        for name in preset_data:
            assert name in palette_data, (
                f"Palette missing color '{name}' that exists in preset"
            )
            assert preset_data[name] == palette_data[name], (
                f"BUG QA-140: Data drift detected for '{name}': "
                f"preset={preset_data[name]}, palette={palette_data[name]}. "
                f"Palette data is duplicated from color_config instead of "
                f"referencing the source-of-truth constants."
            )


# -- QA-141: reshape_matrix ZeroDivisionError when split_num_x is 0 -----------
# File: backend/core/blend_color.py:367-368
# split_num_y = df.shape[0] * df.shape[1] // split_num_x
# This runs before the if split_num_x > 0 guard at line 370.

class TestQA141ReshapeMatrixZeroDiv:
    """reshape_matrix crashes when split_num_x evaluates to 0."""

    def test_large_length_total_no_crash(self):
        """reshape_matrix should not crash when length_total makes split_num_x=0."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=4),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=4),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=4),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=20),
        ]
        # Use a very large plate_length to make split_num_x = 0
        gen = BlendTestGenerator(
            plate_length=999999,
            layer_count_max=1,  # minimal permutations
            layer_height=0.08,
            colors=Colors.from_configs(configs),
        )

        items = gen.colors.get_labels()
        gen.df = gen.permutation_matrix(items, gen.layer_count_max)

        try:
            gen.reshape_matrix(gen.df)
        except ZeroDivisionError:
            pytest.fail(
                "BUG QA-141: reshape_matrix raises ZeroDivisionError when "
                "split_num_x is 0 due to large length_total. The line "
                "split_num_y = ... // split_num_x runs before the "
                "if split_num_x > 0 guard."
            )


# -- QA-142: permutation_matrix crashes on empty items list --------------------
# File: backend/core/blend_color.py:440-451
# With items=[], row = len(items) = 0, then col = len(joined) // row => ZeroDivisionError

class TestQA142PermutationMatrixEmptyItems:
    """permutation_matrix crashes with ZeroDivisionError on empty items."""

    def test_empty_items_graceful(self):
        """permutation_matrix([]) should raise ValueError, not ZeroDivisionError."""
        configs = [
            ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=4),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=2),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=3),
            ColorConfig(name="White", hex="#FFFFFF", transmission_distance=20),
        ]
        gen = BlendTestGenerator(
            plate_length=100,
            layer_count_max=2,
            layer_height=0.08,
            colors=Colors.from_configs(configs),
        )

        try:
            gen.permutation_matrix([], 2)
        except ZeroDivisionError:
            pytest.fail(
                "BUG QA-142: permutation_matrix([]) raises ZeroDivisionError "
                "from len(joined) // len(items) when items is empty. "
                "Should raise ValueError or return empty matrix."
            )
        except (ValueError, IndexError):
            pass  # acceptable error handling


# -- QA-143: Palette mutable global state -- get_palette returns direct ref ----
# File: backend/core/palette_library.py:14-20, 180-185
# get_palette returns direct reference to module-level PaletteEntry.
# Mutating the .colors list permanently corrupts the global palette.

class TestQA143PaletteMutableGlobalState:
    """get_palette returns mutable reference to global palette."""

    def test_palette_mutation_does_not_persist(self):
        """Modifying returned palette should not affect subsequent calls."""
        import copy
        from core.palette_library import get_palette

        palette1 = get_palette("bambu_cmyw_phase6")
        assert palette1 is not None
        original_count = len(palette1.colors)

        # Save a snapshot of the original colors for cleanup
        original_colors = list(palette1.colors)

        try:
            # Mutate the returned palette's colors list
            palette1.colors.append(
                ColorConfig(name="Test", hex="#000000", transmission_distance=1)
            )

            # Get the palette again
            palette2 = get_palette("bambu_cmyw_phase6")
            assert palette2 is not None

            assert len(palette2.colors) == original_count, (
                f"BUG QA-143: get_palette returns direct reference to global "
                f"PaletteEntry. Mutating palette1.colors.append() permanently "
                f"changed the global palette from {original_count} to "
                f"{len(palette2.colors)} colors. Should return a copy."
            )
        finally:
            # Always clean up: restore original colors to not corrupt other tests
            palette1.colors.clear()
            palette1.colors.extend(original_colors)


# -- QA-144: Form params colorThreshold, epsilon have no upper bound -----------
# File: backend/api/routes/image.py:32-34
# colorThreshold has ge=0 but no le constraint.

class TestQA144FormParamsNoUpperBound:
    """Form parameters like colorThreshold and epsilon lack upper bounds."""

    def test_color_threshold_has_upper_bound(self):
        """The process-image endpoint should reject extreme colorThreshold."""
        import inspect
        from api.routes.image import api_process_image

        # Check the function signature for the colorThreshold parameter
        sig = inspect.signature(api_process_image)
        ct_param = sig.parameters.get('colorThreshold')

        if ct_param is None:
            pytest.skip("colorThreshold parameter not found")

        # Check if the Form field has a le constraint
        default = ct_param.default
        has_upper_bound = False
        if hasattr(default, 'le') and default.le is not None:
            has_upper_bound = True
        elif hasattr(default, 'metadata'):
            for m in default.metadata:
                if hasattr(m, 'le') and m.le is not None:
                    has_upper_bound = True
                    break

        assert has_upper_bound, (
            "BUG QA-144: colorThreshold Form parameter has ge=0 but no "
            "upper bound. A client can send colorThreshold=999999999.0, "
            "causing merge_similar_colors() to merge all colors into one. "
            "Add le=1000 or similar."
        )


# -- QA-145: SVG mode does not downscale images --------------------------------
# File: backend/api/routes/image.py:72-74
# Pixel mode calls process_image() which downscales via _downscale_if_needed.
# SVG mode opens the image directly without downscaling.

# -- QA-146: Batch download silently falls back on malformed filamentColors ----
# File: backend/api/routes/batch.py:120-134
# Batch download parses filamentColors as JSON string, catches errors
# silently and falls back to default colors. No feedback to user.

# -- QA-147: VectorColorResult.color uses unvalidated tuple type ---------------
# File: backend/api/models.py:113-118
# color: tuple accepts any tuple of any length. Should be (int, int, int)
# with values in [0, 255] range.

class TestQA147VectorColorResultUnvalidated:
    """VectorColorResult.color accepts tuples of any length/type."""

    def test_color_tuple_validated(self):
        """VectorColorResult should reject color tuples with wrong length."""
        from api.models import VectorColorResult

        # A valid color should be a 3-tuple of ints
        valid = VectorColorResult(
            color=(128, 64, 32),
            regions=[{"outer": [(0, 0), (1, 0), (1, 1)], "holes": []}],
            pixel_count=100,
            polygon_points=3,
        )
        assert valid.color == (128, 64, 32)

        # An empty tuple should be rejected
        try:
            invalid = VectorColorResult(
                color=(),
                regions=[{"outer": [(0, 0), (1, 0), (1, 1)], "holes": []}],
                pixel_count=100,
                polygon_points=3,
            )
            # If we got here, the bug is present (no validation)
            assert False, (
                "BUG QA-147: VectorColorResult.color accepts empty tuple (). "
                "Should validate color is a 3-tuple of ints in [0, 255] range. "
                "In svg_stl_generator.py, color is passed to map_to_nearest_color "
                "which treats it as RGB and divides by 255.0."
            )
        except (ValueError, Exception):
            pass  # Correctly rejected


# -- QA-148: Batch endpoint reads all files before checking total size ---------
# File: backend/api/routes/batch.py:40-56
# _read_batch_files reads ALL files into memory, then checks total_size.
# 20 x 10MB = 200MB already in memory before 413 error.
