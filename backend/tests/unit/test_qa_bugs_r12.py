"""
QA Round 12 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""

import os

import numpy as np
import pytest
import numpy as np

from core.blend_color import Color, Colors, BlendTestGenerator, _code_to_rgb_cached
from core.color_config import ColorConfig

# -- QA-120: Palette library palettes have first-letter collision risk ---------
# File: backend/core/palette_library.py
# Several palettes have colors whose first letters collide:
# - Monochrome: Black (B), Gray (G), Light Gray (L), White (W) — OK
# - Ocean: Deep Blue (D), Teal (T), Aqua (A), White (W) — OK
# BUT if a user applies "CMYK + Black" palette (5 colors: C, M, Y, W, B),
# and the backend creates Colors.from_configs(), it works because labels
# are unique. However, the frontend validation `isFilamentConfigValid`
# also checks unique first letters (case-insensitive), so it should be fine.
#
# The actual issue: Forest palette has "Forest Green" (F), "Brown" (B),
# "Leaf Green" (L), "White" (W) — all unique. BUT if a user customizes
# the palette and changes a color name, the frontend should catch collisions
# immediately. This test verifies all built-in palettes have unique labels.

class TestQA120PaletteLabelsUnique:
    """All palettes must have unique first-letter labels for blend codes."""

    def test_all_palettes_have_unique_labels(self):
        """Every palette's colors must have unique first letters."""
        from core.palette_library import ALL_PALETTES

        for palette in ALL_PALETTES:
            labels = [c.name[0].upper() for c in palette.colors]
            if len(labels) != len(set(labels)):
                dupes = [l for l in labels if labels.count(l) > 1]
                pytest.fail(
                    f"BUG QA-120: Palette '{palette.name}' (id={palette.id}) has "
                    f"duplicate first-letter labels: {dupes}. Colors: "
                    f"{[c.name for c in palette.colors]}. "
                    f"This will cause blend code collisions when applied."
                )


# -- QA-121: Batch processor doesn't forward filamentColors from V2 config -----
# File: backend/api/routes/batch.py:87-99
# Already tracked as QA-115, but here we verify another angle: even when
# using the existing filamentPreset parameter, an invalid preset string
# silently falls through to default colors (line 156: `pass` on ValueError).

# -- QA-122: Color class doesn't validate ASCII labels -------------------------
# File: backend/core/blend_color.py:30
# ColorConfig validates ASCII first-letter, but the Color class itself
# does NOT validate its name starts with ASCII. If Color() is used directly
# (not via ColorConfig/from_configs), non-ASCII labels can enter the system.
# Colors(colors={'Ü': color}) also accepts non-ASCII keys without validation.

class TestQA122ColorClassNoASCIIValidation:
    """Color class doesn't validate that label is ASCII."""

    def test_color_class_accepts_non_ascii_name(self):
        """Color() should reject names that start with non-ASCII characters."""
        try:
            color = Color(name="Über", transmission_distance=3.0, hex="#FF0000")
            label = color.get_label()
            assert label.isascii() and label.isalpha(), (
                f"BUG QA-122: Color class accepts name 'Über' producing "
                f"label '{label}' which is non-ASCII. Only ColorConfig validates "
                f"ASCII labels, but Color() class can be used directly."
            )
        except (ValueError, TypeError):
            pass  # Correctly rejected — not currently the case

    def test_colors_dict_accepts_non_ascii_key(self):
        """Colors(colors=dict) should validate that keys are ASCII."""
        try:
            color = Color(name="Über", transmission_distance=3.0, hex="#FF0000")
            colors = Colors(colors={'Ü': color})
            labels = colors.get_labels()
            assert all(l.isascii() and l.isalpha() for l in labels), (
                f"BUG QA-122: Colors(colors={{}}) accepts non-ASCII keys: {labels}. "
                f"The Colors class doesn't validate keys, so non-ASCII labels "
                f"can enter the system via direct construction."
            )
        except (ValueError, TypeError):
            pass  # Correctly rejected — not currently the case


# -- QA-123: Batch endpoint doesn't validate total file size ------------------
# File: backend/api/routes/batch.py:25-84
# Individual file validation happens via validate_image_upload(), which
# checks per-file size against max_upload_size (10MB). However, there's
# no total batch size check. An attacker could send 20 files × 10MB = 200MB
# in a single request, consuming server memory. The batch processor reads
# ALL files into memory before processing.

# -- QA-124: Palette library colors missing transmission_distance validation ---
# File: backend/core/palette_library.py
# PaletteEntry colors are ColorConfig objects which validate td > 0.
# But the palette data is defined as module-level constants.
# If someone adds a palette with td=0 or negative td, it would crash
# at import time. This test verifies all palettes have valid td values.

class TestQA124PaletteTransmissionDistances:
    """All palette colors should have valid transmission distances."""

    def test_all_palettes_have_valid_transmission_distances(self):
        """Every palette color should have td > 0."""
        from core.palette_library import ALL_PALETTES

        for palette in ALL_PALETTES:
            for color in palette.colors:
                assert np.all(np.isfinite(color.transmission_distance)) and np.all(np.asarray(color.transmission_distance) > 0), (
                    f"Palette '{palette.name}' color '{color.name}' has "
                    f"invalid transmission_distance={color.transmission_distance}"
                )


# -- QA-125: generate_3mf doesn't handle empty pixel lists for color blocks ----
# File: backend/services/threemf_generator.py:119
# If a color block has an empty pixel list (which shouldn't happen due to
# model validation, but could happen in internal calls), the loop
# `for pixel in pixels` produces no meshes, but the code_char still gets
# an entry in code_mesh_map. This is harmless but wasteful.
# More importantly: if `blend_code` contains characters NOT in code_mesh_map
# (labels), line 134 will raise a KeyError.

class TestQA125ThreeMFUnknownBlendCodeChar:
    """3MF generator should handle blend codes with chars not in labels."""

    def test_blend_code_char_always_in_label_map(self):
        """All blend code characters should exist in the color labels."""
        from services.threemf_generator import generate_3mf
        from services.stl_generator import compute_reference_matrices

        colors = Colors()
        ref_code, ref_rgb = compute_reference_matrices(4, 0.08, colors)

        # Get all possible blend codes from the reference matrix
        all_codes = set()
        for r in range(ref_code.shape[0]):
            for c in range(ref_code.shape[1]):
                code = ref_code.iat[r, c]
                for char in code:
                    all_codes.add(char)

        labels = set(colors.get_labels())

        assert all_codes.issubset(labels), (
            f"Reference matrix contains code chars {all_codes - labels} "
            f"not in color labels {labels}. This would cause KeyError in "
            f"threemf_generator code_mesh_map lookup."
        )


# -- QA-126: DownloadSTLRequestV2 max_length=16 but header says 4-10 ----------
# File: backend/api/models.py:158-162
# The docstring says "Custom filament colors (4-16 colors)" but the
# endpoint docstring in download_v2.py:120 says "4-10 colors". This
# inconsistency could confuse API users.

class TestQA126DocumentedColorLimitMismatch:
    """Model and endpoint docs disagree on max filament colors."""

    def test_model_max_length_matches_documentation(self):
        """Verify the actual max_length on filamentColors field."""
        from api.models import DownloadSTLRequestV2

        field_info = DownloadSTLRequestV2.model_fields['filamentColors']
        metadata = field_info.metadata if hasattr(field_info, 'metadata') else []

        # The actual max_length should be consistent
        max_len = getattr(field_info, 'max_length', None)
        if max_len is None:
            for m in metadata:
                if hasattr(m, 'max_length'):
                    max_len = m.max_length
                    break

        # Check route docstring
        from api.routes.download_v2 import api_download_stl_v2
        docstring = api_download_stl_v2.__doc__ or ''

        if '4-10' in docstring and max_len == 16:
            pytest.fail(
                "BUG QA-126: api_download_stl_v2 docstring says '4-10 colors' "
                f"but DownloadSTLRequestV2.filamentColors has max_length={max_len}. "
                "This documentation mismatch confuses API consumers."
            )


class TestBatchInvalidPresetRejected:
    """Invalid batch preset must 400 with the valid list, not fall back (QA-121)."""

    def test_batch_download_invalid_preset_returns_400(self):
        from fastapi.testclient import TestClient
        from main import app

        fixture = os.path.join(
            os.path.dirname(__file__), "..", "fixtures", "images", "perf_cmywk.jpg"
        )
        with open(fixture, "rb") as f:
            image_bytes = f.read()

        client = TestClient(app)
        resp = client.post(
            "/api/batch/download-stl",
            files=[("images", ("t.jpg", image_bytes, "image/jpeg"))],
            data={"filamentPreset": "nope", "layerCount": "4"},
        )
        assert resp.status_code == 400
        assert "Invalid filament preset" in str(resp.json()["detail"])
