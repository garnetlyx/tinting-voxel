"""
QA Round 12 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import inspect
import json
import re

import numpy as np
import pytest

from core.blend_color import Color, Colors, BlendTestGenerator, _code_to_rgb_cached
from core.color_config import ColorConfig


# -- QA-116: SVG STL download never sends doubleSided from frontend ------------
# File: src/hooks/useImageProcessor.ts:362-366
# In handleDownloadSTL, the SVG mode branch calls downloadSVGSTLV2 but
# omits the `doubleSided` parameter that the pixel mode branch includes.
# Backend endpoint DownloadSVGSTLRequestV2 has the field, but frontend
# never sends it, so double-sided prints are silently single-sided in SVG mode.
#
# This is a frontend-only bug; we document it here and test the backend side
# works correctly (SVG V2 model has doubleSided field).

class TestQA116SVGDownloadMissingDoubleSided:
    """Frontend SVG STL download omits doubleSided parameter."""

    def test_svg_v2_model_accepts_double_sided(self):
        """DownloadSVGSTLRequestV2 should accept doubleSided field."""
        from api.models import DownloadSVGSTLRequestV2

        # Verify the model has the field and can be set
        fields = DownloadSVGSTLRequestV2.model_fields
        assert 'doubleSided' in fields, (
            "BUG QA-116: DownloadSVGSTLRequestV2 should have doubleSided field"
        )

    def test_frontend_sends_double_sided_in_svg_mode(self):
        """Frontend SVG download should include doubleSided (source code check)."""
        import os
        hook_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'src', 'hooks', 'useImageProcessor.ts'
        )
        if not os.path.exists(hook_path):
            pytest.skip("Frontend source not available")

        with open(hook_path) as f:
            source = f.read()

        # Find the actual downloadSVGSTLV2 function call (not the import)
        # Look for 'await downloadSVGSTLV2(' pattern
        svg_call_start = source.find('await downloadSVGSTLV2(')
        if svg_call_start == -1:
            pytest.skip("await downloadSVGSTLV2 call not found")

        # Extract the call arguments block (from call to closing brace)
        svg_section = source[svg_call_start:svg_call_start + 500]

        assert 'doubleSided' in svg_section, (
            "BUG QA-116: Frontend downloadSVGSTLV2 call in useImageProcessor.ts "
            "does not include doubleSided parameter. SVG mode silently ignores "
            "the double-sided toggle. Compare with pixel mode which passes "
            "doubleSided: doubleSided || undefined."
        )


# -- QA-117: print_settings_generator ignores double_sided for height ----------
# File: backend/services/print_settings_generator.py:45
# total_height_mm = layer_count * layer_height
# When double_sided=True, the total height should double the layer portion:
# total = 2 * layer_count * layer_height
# Currently the output is wrong for double-sided prints.

class TestQA117PrintSettingsDoubleSidedHeight:
    """Print settings total_height_mm doesn't account for double-sided."""

    def test_double_sided_height_is_doubled(self):
        """Total height should include both front and back layers."""
        from services.print_settings_generator import generate_print_settings

        single_json = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#00FFFF', 'transmission_distance': 3.0},
                {'name': 'Magenta', 'hex': '#FF00FF', 'transmission_distance': 1.9},
                {'name': 'Yellow', 'hex': '#FFFF00', 'transmission_distance': 2.5},
                {'name': 'White', 'hex': '#FFFFFF', 'transmission_distance': 7.2},
            ],
            double_sided=False,
        )

        double_json = generate_print_settings(
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 10, 'height': 10},
            filament_colors=[
                {'name': 'Cyan', 'hex': '#00FFFF', 'transmission_distance': 3.0},
                {'name': 'Magenta', 'hex': '#FF00FF', 'transmission_distance': 1.9},
                {'name': 'Yellow', 'hex': '#FFFF00', 'transmission_distance': 2.5},
                {'name': 'White', 'hex': '#FFFFFF', 'transmission_distance': 7.2},
            ],
            double_sided=True,
        )

        single = json.loads(single_json)
        double = json.loads(double_json)

        single_height = single['object_dimensions']['total_height_mm']
        double_height = double['object_dimensions']['total_height_mm']

        # Double-sided should be approximately twice the layer height
        expected_double_height = round(2 * 4 * 0.08, 2)
        expected_single_height = round(4 * 0.08, 2)

        assert double_height > single_height, (
            f"BUG QA-117: Print settings total_height_mm is {double_height} for "
            f"double-sided, same as {single_height} for single-sided. "
            f"Double-sided total height should be {expected_double_height}mm "
            f"(2 x {expected_single_height}mm layers) but got {double_height}mm."
        )


# -- QA-118: ThreeDPreview showExploded state is unused -------------------------
# File: src/components/ThreeDPreview.tsx:165, 422-429
# The Exploded view button toggles `showExploded` state, but
# buildInstancedMeshes() never receives or uses it. Clicking the button
# does nothing visually. This is a frontend-only bug.

class TestQA118ExplodedViewUnused:
    """ThreeDPreview Exploded button toggles state that is never used."""

    def test_exploded_state_connected_to_build_function(self):
        """showExploded should be passed to the mesh building function."""
        import os
        component_path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..', 'src', 'components', 'ThreeDPreview.tsx'
        )
        if not os.path.exists(component_path):
            pytest.skip("Frontend source not available")

        with open(component_path) as f:
            source = f.read()

        # Find the call site for buildInstancedMeshes (after useMemo)
        call_idx = source.find('const group = buildInstancedMeshes(')
        if call_idx == -1:
            pytest.skip("buildInstancedMeshes call not found")

        # Check the 400 chars after the call
        call_section = source[call_idx:call_idx + 400]

        # QA-118 was fixed: buildInstancedMeshes now accepts showExploded param
        # and the feature is fully implemented with layer separation
        assert 'showExploded' in call_section, (
            "BUG QA-118: ThreeDPreview has an 'Exploded' button that toggles "
            "showExploded state. buildInstancedMeshes() should receive this "
            "parameter and render voxels with layer gaps in exploded view."
        )


# -- QA-119: analytics middleware creates unbounded key growth -----------------
# File: backend/services/analytics.py, backend/main.py:85-93
# The analytics middleware records `path = request.url.path` directly.
# For endpoints with path parameters like /api/palettes/{palette_id},
# each unique palette_id creates a new key in the analytics dict.
# An attacker could send requests to /api/palettes/<random-uuid> thousands
# of times, each creating a unique key and consuming server memory.

class TestQA119AnalyticsUnboundedKeyGrowth:
    """Analytics records parameterized paths verbatim, causing memory growth."""

    def test_parameterized_paths_normalized(self):
        """Analytics should normalize parameterized paths to prevent key explosion."""
        from services.analytics import AnalyticsCollector

        collector = AnalyticsCollector()

        # Simulate 100 requests with different palette IDs
        for i in range(100):
            collector.record_request(
                method="GET",
                path=f"/api/palettes/fake-palette-{i}",
                status_code=404,
                response_time_ms=10.0,
            )

        summary = collector.get_summary()
        endpoint_count = len(summary['endpoints'])

        # If paths are not normalized, we get 100 unique keys
        # If they are, we should get 1 key like "GET /api/palettes/{id}"
        assert endpoint_count < 10, (
            f"BUG QA-119: Analytics recorded {endpoint_count} unique endpoint keys "
            f"for 100 requests to /api/palettes/<unique-id>. Each unique path "
            f"parameter creates a new dictionary key, causing unbounded memory "
            f"growth. Paths with parameters should be normalized (e.g., "
            f"/api/palettes/{{id}})."
        )

        collector.reset()


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

class TestQA121BatchInvalidPresetSilentFallback:
    """Batch download silently uses default colors for invalid preset names."""

    def test_invalid_preset_rejected_not_silently_ignored(self):
        """An invalid filamentPreset should either error or be clearly documented."""
        from api.routes.batch import api_batch_download_stl
        source = inspect.getsource(api_batch_download_stl)

        # Check if there's a `pass` after ValueError catch for invalid preset
        has_silent_pass = re.search(r'except ValueError:\s*\n\s*pass', source)

        assert not has_silent_pass, (
            "BUG QA-121: Batch download endpoint silently ignores invalid "
            "filamentPreset values (catches ValueError and does `pass`). "
            "If a user sends filamentPreset='nonexistent', they silently "
            "get default CMYK colors instead of an error. This should either "
            "return a 400 error or at least log a warning that's visible."
        )


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

class TestQA123BatchNoTotalSizeLimit:
    """Batch endpoint has no total file size limit."""

    def test_batch_process_checks_total_size(self):
        """Batch processing should enforce a total size limit."""
        # Check the batch module for total size enforcement
        # (may be in route function or helper like _read_batch_files)
        from api.routes import batch
        module_source = inspect.getsource(batch)

        has_total_size_check = (
            'total_size' in module_source or
            'total_bytes' in module_source or
            'MAX_TOTAL_BATCH_SIZE' in module_source
        )

        assert has_total_size_check, (
            "BUG QA-123: Batch endpoints have no total file size limit. "
            "Individual files are validated (max 10MB each) but 20 files × 10MB "
            "= 200MB total can be sent in a single request. All files are read "
            "into memory at once. Should enforce a total batch size limit."
        )


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
                assert color.transmission_distance > 0, (
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
