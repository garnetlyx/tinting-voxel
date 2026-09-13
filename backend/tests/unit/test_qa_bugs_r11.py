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
