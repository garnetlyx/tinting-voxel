"""
QA Round 11 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import inspect
import re

import numpy as np
import pytest

from core.blend_color import Color, Colors, BlendTestGenerator
from core.color_config import ColorConfig


# -- QA-107: SVG STL generator ignores double_sided parameter ------------------
# File: backend/services/svg_stl_generator.py:206-329
# The function signature accepts `double_sided: bool = False` but NEVER
# uses the parameter in the function body. The pixel-mode STL generator
# (stl_generator.py) correctly implements double-sided by mirroring polygons
# and stacking reversed layers. SVG mode silently drops the flag.

class TestQA107SVGDoubleSidedIgnored:
    """generate_svg_stl_zip accepts double_sided but never uses it."""

    def test_svg_double_sided_produces_more_data(self):
        """Double-sided SVG STL should be larger than single-sided."""
        from services.svg_stl_generator import generate_svg_stl_zip

        vector_results = [
            {
                'color': (0, 255, 255),
                'polygons': [[(0, 0), (10, 0), (10, 10), (0, 10)]],
                'pixel_count': 100,
                'polygon_points': 4,
            }
        ]
        image_dims = {'width': 10, 'height': 10}
        colors = Colors()

        single = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions=image_dims,
            colors=colors,
            double_sided=False,
        )

        double = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions=image_dims,
            colors=colors,
            double_sided=True,
        )

        assert len(double) > len(single), (
            f"BUG QA-107: generate_svg_stl_zip ignores double_sided parameter. "
            f"Single-sided ZIP = {len(single)} bytes, double-sided ZIP = {len(double)} bytes. "
            f"They should differ because double-sided adds mirrored back layers."
        )

    def test_svg_double_sided_code_actually_used(self):
        """The double_sided parameter should be referenced in the function body."""
        from services import svg_stl_generator
        source = inspect.getsource(svg_stl_generator.generate_svg_stl_zip)

        # Remove the signature and docstring to check only the body
        body_start = source.index('"""', source.index('"""') + 3) + 3
        body = source[body_start:]

        assert 'double_sided' in body, (
            f"BUG QA-107: generate_svg_stl_zip function body never references "
            f"'double_sided'. The parameter is accepted but silently ignored."
        )


# -- QA-109: WebP not supported despite frontend accepting it -----------------
# File: backend/api/validators.py:11-16, backend/config/settings.py:44
# The frontend (QA-FE-09 fix) validates file types as:
#   ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp']
# But the backend:
#   - allowed_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".gif"]  (no .webp)
#   - IMAGE_MAGIC_BYTES doesn't include WebP ('RIFF....WEBP')
# A user uploading a .webp file gets an unhelpful "Unsupported file type" error.

class TestQA109WebPNotSupported:
    """WebP uploads are rejected by backend despite frontend accepting them."""

    def test_webp_extension_allowed(self):
        """Backend should accept .webp file extension."""
        from config.settings import settings

        assert '.webp' in settings.allowed_extensions, (
            f"BUG QA-109: Backend allowed_extensions = {settings.allowed_extensions} "
            f"does not include '.webp'. Frontend accepts 'image/webp' uploads, "
            f"causing a mismatch where valid user uploads are rejected at the backend."
        )

    def test_webp_magic_bytes_recognized(self):
        """Backend should recognize WebP magic bytes."""
        from api.validators import IMAGE_MAGIC_BYTES

        # WebP files start with 'RIFF' header followed by file size and 'WEBP'
        webp_magics = [m for m in IMAGE_MAGIC_BYTES if b'WEBP' in m or b'RIFF' in m]
        assert len(webp_magics) > 0, (
            f"BUG QA-109: IMAGE_MAGIC_BYTES does not include WebP format. "
            f"WebP files start with RIFF....WEBP header, which is not recognized. "
            f"Current magic bytes: {list(IMAGE_MAGIC_BYTES.values())}"
        )


# -- QA-110: FilamentColorConfig.label collisions not caught for multi-char ---
# File: backend/api/models.py:44-46
# The label property returns `self.name[0].upper()`, using only the first char.
# A color named with emoji like "🔴Red" produces label '🔴', which when used
# as a blend code character works but violates the implicit ASCII assumption
# throughout the codebase.

class TestQA110UnicodeColorLabelBreaksBlendCode:
    """Unicode first-char labels break the implicit ASCII label assumption."""

    def test_emoji_name_label_used_in_blend_code(self):
        """A color name starting with emoji should be caught during validation."""
        # ColorConfig should reject emoji-first names during validation
        with pytest.raises(ValueError, match="must start with an ASCII letter"):
            config = ColorConfig(
                name="🔴Red",
                hex="#FF0000",
                transmission_distance=2.0,
            )
            colors = Colors.from_configs([
                config,
                ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
                ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
                ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
            ])


# -- QA-111: Batch download silently swallows individual STL generation errors -
# File: backend/services/batch_processor.py:140-143
# When generate_stl_zip raises an exception for one image in the batch,
# the error is only logged and the image is silently skipped.
# If ALL images fail, an empty 22-byte ZIP is returned instead of raising.

class TestQA111BatchSTLSilentFailure:
    """generate_batch_stl_zip silently skips failed images and can return empty ZIP."""

    def test_all_stl_failures_returns_nonempty_or_raises(self):
        """If all image STL generations fail, should raise not return empty ZIP."""
        from services.batch_processor import generate_batch_stl_zip

        # Provide invalid results that will cause generate_stl_zip to fail
        invalid_results = [
            {
                'filename': 'broken1.png',
                'status': 'success',
                'colorBlocks': [{'invalid': 'data'}],
                'imageDimensions': {'width': 10, 'height': 10},
            },
            {
                'filename': 'broken2.png',
                'status': 'success',
                'colorBlocks': [{'also': 'invalid'}],
                'imageDimensions': {'width': 10, 'height': 10},
            },
        ]

        # An empty ZIP is just the end-of-central-directory record (~22 bytes)
        # This should either raise or return a non-trivial ZIP
        with pytest.raises(ValueError, match="Failed to generate STL files for all"):
            result = generate_batch_stl_zip(
                batch_results=invalid_results,
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
            )


# -- QA-112: FilamentColorConfig.name has no max_length -----------------------
# File: backend/api/models.py:18
# The name field has min_length=1 but no max_length. A malicious request
# could send a name with millions of characters, consuming memory.

class TestQA112FilamentNameNoMaxLength:
    """FilamentColorConfig name field has no upper length bound."""

    def test_name_field_has_max_length(self):
        """FilamentColorConfig.name should have a max_length constraint."""
        from api.models import FilamentColorConfig

        # Check that the model field definition includes max_length
        # In Pydantic V2, use model_fields instead of __fields__
        name_field = FilamentColorConfig.model_fields['name']
        # max_length is stored in the metadata of the Field
        max_len = None
        if hasattr(name_field, 'metadata'):
            for m in name_field.metadata:
                if hasattr(m, 'max_length'):
                    max_len = m.max_length
                    break

        assert max_len is not None and max_len <= 200, (
            f"BUG QA-112: FilamentColorConfig.name has no max_length constraint. "
            f"A malicious request can send arbitrarily long names (tested 10K chars), "
            f"wasting memory. Should have max_length=100 or similar."
        )


# -- QA-113: _code_to_rgb_cached alpha inconsistency -------------------------
# File: backend/core/blend_color.py:187
# In _code_to_rgb_cached, alpha=23 is hardcoded, but in
# Color.get_transmission_rate the default alpha=12.
# This means the same (layer_height, transmission_distance) pair gives
# different transmission rates depending on the code path.

class TestQA113AlphaInconsistency:
    """_code_to_rgb_cached uses alpha=23 but get_transmission_rate defaults to alpha=12."""

    def test_code_to_rgb_alpha_matches_default(self):
        """The alpha value used in code_to_rgb should match get_transmission_rate default."""
        source = inspect.getsource(Color.get_transmission_rate)

        # Extract default alpha from get_transmission_rate signature (handles 12 or 12.0)
        # Pattern must account for optional type annotations like "alpha: float = 12.0"
        match = re.search(r'alpha[^=\n]*=\s*(\d+(?:\.\d+)?)', source)
        default_alpha = float(match.group(1)) if match else None

        from core.blend_color import _code_to_rgb_cached
        cached_source = inspect.getsource(_code_to_rgb_cached)

        # Extract alpha from _code_to_rgb_cached signature (handles 12 or 12.0)
        match2 = re.search(r'alpha[^=\n]*=\s*(\d+(?:\.\d+)?)', cached_source)
        cached_alpha = float(match2.group(1)) if match2 else None

        assert default_alpha == cached_alpha, (
            f"BUG QA-113: Alpha inconsistency. "
            f"Color.get_transmission_rate defaults to alpha={default_alpha}, "
            f"but _code_to_rgb_cached uses alpha={cached_alpha}. "
            f"This means code_to_rgb produces different optical blending results "
            f"than direct get_transmission_rate calls with the same parameters."
        )


# -- QA-114: SVG physical_height doesn't account for double_sided ------------
# File: backend/services/svg_stl_generator.py:301
# Even once QA-107 is fixed, the physical_height used for filenames
# should be doubled for double-sided mode (as stl_generator.py does).

class TestQA114SVGPhysicalHeightDoubleSided:
    """SVG STL filename doesn't account for doubled height in double-sided mode."""

    def test_physical_height_includes_both_sides(self):
        """In double-sided mode, physical height calculation should account for both sides."""
        from services import svg_stl_generator
        source = inspect.getsource(svg_stl_generator.generate_svg_stl_zip)

        has_doubled = (
            'layer_count * 2' in source or
            'effective_layer_count' in source or
            '2 *' in source
        )

        assert has_doubled, (
            f"BUG QA-114: generate_svg_stl_zip does not calculate "
            f"physical_height accounting for double-sided mode. "
            f"Pixel-mode uses `layer_count * 2 if double_sided`, but SVG mode "
            f"always uses `layer_count * layer_height`, producing wrong filenames."
        )


# -- QA-115: batch download route doesn't support custom filamentColors -------
# File: backend/api/routes/batch.py:87-99
# The batch download endpoint only accepts `filamentPreset: Optional[str]`
# but not `filamentColors`. V2 download endpoints support both.

class TestQA115BatchNoCustomColors:
    """Batch download endpoint doesn't support custom filament colors."""

    def test_batch_download_has_filament_colors_param(self):
        """api_batch_download_stl should accept filamentColors like V2 endpoints."""
        from api.routes import batch
        source = inspect.getsource(batch.api_batch_download_stl)

        assert 'filamentColors' in source, (
            f"BUG QA-115: batch download endpoint /api/batch/download-stl "
            f"only supports filamentPreset, not filamentColors. "
            f"Users with custom filament configurations cannot use batch mode. "
            f"V2 endpoints support both preset and custom colors."
        )
