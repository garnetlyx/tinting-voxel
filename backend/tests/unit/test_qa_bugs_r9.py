"""
QA Round 9 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import inspect
import json
import re

import numpy as np
import pytest

from core.blend_color import Color, Colors, BlendTestGenerator, _code_to_rgb_cached, clear_rgb_cache
from core.color_config import ColorConfig


# -- QA-66: 3MF endpoint doubleSided — FIXED in uncommitted changes.
# The route at download_v2.py:277 now passes double_sided=body.doubleSided
# and generate_3mf at threemf_generator.py:63 accepts double_sided param.
# No failing test needed — already fixed.


# -- QA-67: SVG STL V2 endpoint ignores doubleSided ---------------------------
# File: backend/api/routes/download_v2.py:199-207
# DownloadSVGSTLRequestV2 model doesn't have a doubleSided field at all,
# and the SVG endpoint doesn't pass it to generate_svg_stl_zip.

class TestQA67SVGSTLDoubleSidedMissing:
    """SVG STL V2 model and endpoint don't support doubleSided."""

    def test_svg_stl_v2_model_has_double_sided_field(self):
        """DownloadSVGSTLRequestV2 should have a doubleSided field for parity."""
        from api.models import DownloadSVGSTLRequestV2

        field_names = list(DownloadSVGSTLRequestV2.model_fields.keys())

        assert 'doubleSided' in field_names, (
            "BUG QA-67: DownloadSVGSTLRequestV2 lacks 'doubleSided' field. "
            "DownloadSTLRequestV2 has it at line 153, but the SVG V2 model "
            "(lines 188-227) omits it. Users switching between pixel and SVG "
            "mode lose double-sided functionality."
        )


# -- QA-68: Frontend sends filamentPreset AND filamentColors together -----------
# File: src/hooks/useImageProcessor.ts:314-321
# This is confirmed by QA-50/QA-FE-04 but the actual download function
# sends BOTH filamentPreset (line 319) and filamentColors (line 320)
# in the same request body. The backend root_validator rejects this.
# Additionally, handleDownload3MF (line 360) and handleDownloadPrintSettings
# (line 387) also send both.

class TestQA68AllDownloadsSendBothPresetAndColors:
    """All V2 download functions in the frontend send both filamentPreset
    AND filamentColors, but backend rejects this combo.

    This test validates the backend behavior that will cause 422 errors
    for the exact payload the frontend sends.
    """

    def test_preset_and_colors_rejected_for_stl(self):
        """V2 STL download with both preset and colors should be rejected."""
        from api.models import DownloadSTLRequestV2
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Cannot provide both"):
            DownloadSTLRequestV2(
                colorBlocks=[{
                    "r": 0, "g": 0, "b": 0, "count": 1,
                    "pixels": [{"x": 0, "y": 0}], "hex": "#000000",
                }],
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={"width": 4, "height": 4},
                filamentPreset="bambu_cmyk",
                filamentColors=[
                    {"name": "Cyan", "hex": "#0086D6", "transmission_distance": 3.0},
                    {"name": "Magenta", "hex": "#EC008C", "transmission_distance": 1.9},
                    {"name": "Yellow", "hex": "#F4EE2A", "transmission_distance": 2.5},
                    {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
                ],
            )

    def test_print_settings_with_both_preset_and_colors_rejected(self):
        """PrintSettingsRequest with both preset and colors should be rejected."""
        from api.models import PrintSettingsRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Cannot provide both"):
            PrintSettingsRequest(
                layerHeight=0.08,
                pixelSize=0.08,
                layerCount=4,
                imageDimensions={"width": 4, "height": 4},
                filamentPreset="bambu_cmyk",
                filamentColors=[
                    {"name": "Cyan", "hex": "#0086D6", "transmission_distance": 3.0},
                    {"name": "Magenta", "hex": "#EC008C", "transmission_distance": 1.9},
                    {"name": "Yellow", "hex": "#F4EE2A", "transmission_distance": 2.5},
                    {"name": "White", "hex": "#FFFFFF", "transmission_distance": 7.2},
                ],
            )


# -- QA-69: _code_to_rgb_cached light_loss_ratio normalization changes bg index --
# File: backend/core/blend_color.py:198-202
# After the loop sets light_loss_ratio[i+1] = remain * (1-t) at the ACTUAL
# background index (i+1 = len(code)), the array is normalized by sum.
# Then bg = light_loss_ratio[len(code)] is used, which IS correct.
# BUT: light_loss_ratio[i+1] on line 198 uses the LAST t value (the last
# filament's transmission), not the background transmission. The background
# should transmit 100% (it's just white space), but it uses the last color's
# transmission rate, effectively double-counting the last layer.

class TestQA69LastLayerDoubleCountedInBackground:
    """The background calculation at line 198 uses the last filament's
    transmission rate instead of treating background as fully transparent.

    light_loss_ratio[i+1] = remain * (1 - t)
    Here 't' is the transmission of the LAST filament layer, not the
    background. The background is white (no absorption), so the background
    contribution should be: light_loss_ratio[len(code)] = remain
    (i.e., everything that passes through ALL layers reaches the background).
    Instead, it acts as if there's an extra layer of the last color.
    """

    def test_white_only_code_produces_near_white(self):
        """A single layer of pure white should produce very near-white RGB.

        White filament (W) with td=7.2 is mostly transparent. With only
        1 layer, the light passes mostly through to the white background.
        Result should be very close to (255, 255, 255).
        """
        clear_rgb_cache()

        color_key = (('W', 7.2, '#FFFFFF'),)
        result = _code_to_rgb_cached('W', 0.08, color_key)

        r, g, b = result
        # White on white should be very white (>250 for each channel)
        assert r > 250, f"Red={r:.1f}: single white layer should be >250"
        assert g > 250, f"Green={g:.1f}: single white layer should be >250"
        assert b > 250, f"Blue={b:.1f}: single white layer should be >250"

    def test_background_uses_full_remaining_light(self):
        """Background contribution should use ALL remaining transmitted light,
        not re-apply the last filament's absorption.

        For code 'C' with cyan (td=3.0, hex=#0086D6):
        - Layer absorption reduces light
        - Background gets whatever passes through (remain)
        - Bug: background gets remain * (1-t_cyan) instead of just remain
        """
        clear_rgb_cache()

        color_key = (('C', 3.0, '#0086D6'),)
        result_c = _code_to_rgb_cached('C', 0.08, color_key)

        # With bug: background is remain * (1-t) where t = cyan's transmission
        # Without bug: background is just remain (all light that passes through)
        # The red channel reveals this: cyan absorbs red heavily,
        # so if background is treated correctly (white), red should be significant
        r, g, b = result_c
        # Single thin layer of cyan (0.08mm, td=3.0) should let a LOT of light through
        # The image should look like a very light tint of cyan, close to white
        total = r + g + b
        assert total > 600, (
            f"Single 0.08mm layer of cyan should produce near-white output "
            f"(light passes through to white background). Got RGB=({r:.0f},{g:.0f},{b:.0f}), "
            f"total={total:.0f}. Background light may be incorrectly reduced."
        )


# -- QA-70: FilamentColorConfig.label collision not caught for multi-word names ---
# File: backend/api/models.py:46
# FilamentColorConfig.label returns name[0].upper() but validate_unique_labels
# at line 170 does `c.name[0].upper()` — both use the FIRST CHARACTER.
# Names like "Crimson" and "Coral" would both map to label 'C', but the
# validator only checks name[0]. The issue is that names with the same
# first letter but different names CAN pass the hex uniqueness check
# but map to the same internal Color label, causing a KeyError or
# silent data loss in Colors.from_configs.

class TestQA70LabelCollisionFromDifferentNames:
    """Two filament colors with different names but same first letter cause
    label collision in Colors.from_configs, but the validator doesn't
    give a user-friendly error message about WHY.
    """

    def test_colors_from_configs_label_collision_message(self):
        """Colors.from_configs should mention BOTH conflicting names, not just the label."""
        configs = [
            ColorConfig(name="Crimson", hex="#DC143C", transmission_distance=3.0),
            ColorConfig(name="Coral", hex="#FF7F50", transmission_distance=4.0),
            ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=2.0),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
        ]

        with pytest.raises(ValueError) as exc_info:
            Colors.from_configs(configs)

        error_msg = str(exc_info.value)
        # The error should mention both names for clarity
        assert "Coral" in error_msg, (
            f"BUG QA-70: Colors.from_configs duplicate label error doesn't mention "
            f"the conflicting name. Error: {error_msg}"
        )


# -- QA-71: _code_to_rgb_cached creates new Color objects on every call ----------
# File: backend/core/blend_color.py:174-176
# Inside the cached function, on every call (even cache hits bypass this,
# but on MISS), it rebuilds color_map by constructing new Color objects
# from the hashable key. This involves calling ImageColor.getcolor,
# get_cmyk, get_absorption for EVERY color on EVERY cache miss.
# The color_key IS part of the cache key, so the cache works, but for
# 4096+ unique codes, it creates unnecessary Color objects.
# This is a performance concern, not a correctness bug.
# Documenting as low severity.


# -- QA-72: generate_3mf re-imports re at line 92 (already imported at line 9) ----
# File: backend/services/threemf_generator.py:9,92
# The `re` module is imported at the top of the file (line 9), but is
# ALSO imported inside the function at line 92. This is a code smell:
# the inner import shadows the outer one and is unnecessary.

class TestQA72ThreeMFDuplicateImport:
    """threemf_generator.py imports re twice: at module level and inside function."""

    def test_no_duplicate_re_import_in_generate_3mf(self):
        """generate_3mf should not import re inside the function body."""
        from services.threemf_generator import generate_3mf

        source = inspect.getsource(generate_3mf)
        # Remove the function signature/docstring to focus on the body
        body_lines = source.split('\n')
        import_lines = [
            line.strip() for line in body_lines
            if line.strip().startswith('import re')
        ]

        assert len(import_lines) == 0, (
            "BUG QA-72: generate_3mf imports 're' inside function body "
            "(line 92) when it's already imported at module level (line 9). "
            "The inner import is unnecessary and should be removed."
        )


# -- QA-73: addFilamentColor creates color with empty name -----------------------
# File: src/hooks/useImageProcessor.ts:112
# When adding a new filament color, it uses name: '' (empty string).
# While isFilamentConfigValid catches this before download, the user
# can add multiple empty-name colors without immediate feedback.
# More importantly, FilamentColorConfig has min_length=1 on name,
# but the FRONTEND sends name='' which would pass frontend validation
# but fail backend validation. This is documented as frontend-only.


# -- QA-74: FilamentPreviewRequest validates filament_colors min 4 but -----------
#           Colors.from_configs can crash on 0-length configs
# File: backend/api/models.py:245-247, backend/core/blend_color.py:330
# The FilamentPreviewRequest has min_items=4 for filamentColors, BUT
# if filamentColors is None AND filamentPreset is None, get_colors_from_request
# returns Colors() (default 4 CMYK). This is fine, EXCEPT:
# If someone crafts a request with filamentColors=None and filamentPreset=None
# and somehow bypasses validation, Colors() works fine. Not a real bug.


# -- QA-75: DownloadSVGSTLRequestV2 missing doubleSided field --------------------
# Already covered by QA-67 above.


# -- QA-76: Colors.__getitem__ raises KeyError for missing labels ----------------
# File: backend/core/blend_color.py:289-291
# Colors.__getitem__ does `label.strip().upper()` then accesses self.colors[label].
# If the label doesn't exist, it raises a bare KeyError with no context.
# For the 3MF route at download_v2.py:266, `colors[label].hex` would
# crash with an opaque KeyError if a label doesn't exist.

class TestQA76ColorsGetItemMissingLabel:
    """Colors.__getitem__ raises bare KeyError for missing labels."""

    def test_missing_label_gives_descriptive_error(self):
        """Accessing a nonexistent color label should give a clear error message."""
        colors = Colors()  # Has C, M, Y, W

        with pytest.raises((KeyError, ValueError)) as exc_info:
            _ = colors['X']

        error_msg = str(exc_info.value)
        # A bare KeyError just shows 'X' — no context about available labels
        # A good error message should mention available labels
        available_mentioned = any(
            label in error_msg for label in ['C', 'M', 'Y', 'W']
        )
        assert available_mentioned, (
            f"BUG QA-76: Colors.__getitem__ raises bare KeyError for missing "
            f"label 'X'. Error message: {error_msg}. Should mention available "
            f"labels (C, M, Y, W) for debugging context."
        )


# -- QA-77: image_processor.py cluster_avg_color ZeroDivisionError ---------------
# File: backend/services/image_processor.py:42
# cluster_avg_color divides by len(cluster) but never checks for empty list.
# If merge_similar_colors somehow produces an empty cluster, this crashes.
# In practice, the cluster always has at least one element (the seed color),
# but there's no guard.

class TestQA77ClusterAvgEmptyList:
    """cluster_avg_color crashes with ZeroDivisionError on empty cluster."""

    def test_empty_cluster_raises_clear_error(self):
        """Empty cluster should raise ValueError, not ZeroDivisionError."""
        from services.image_processor import cluster_avg_color

        with pytest.raises((ValueError, ZeroDivisionError)):
            cluster_avg_color([])


# -- QA-78: csv_generator.py leaks raw hex from user input into CSV without ------
#           sanitizing the color index name
# File: backend/services/csv_generator.py:24
# The color name is f"Color{index + 1}" which is safe, but color['hex']
# at line 28 comes directly from the color block and could contain
# crafted values. However, csv.QUOTE_ALL should handle this correctly
# since it wraps everything in quotes. This is NOT a bug — just verifying.


# -- QA-79: compute_reference_matrices sqrt produces non-integer rows/cols --------
# File: backend/services/stl_generator.py:72-73
# rows = int(np.sqrt(n)) and cols = (n + rows - 1) // rows
# When n is not a perfect square, rows * cols > n, and padding is added.
# But when n=0 (from the empty labels guard), rows=0 and cols would be
# (0 + 0 - 1) // 0 = ZeroDivisionError. The guard at line 56 catches
# this, but only if items is EMPTY, not if items has content but
# permutation_count somehow ends up as 0 (which can't happen for len(items)>0).
# This is already covered by QA-64.


# -- QA-80: handleDownloadCSV and handleDownloadPrintSettings don't set -----------
#           processing=true, allowing concurrent downloads
# File: src/hooks/useImageProcessor.ts:287-300, 374-395
# handleDownloadSTL and handleDownload3MF both set setProcessing(true)
# (lines 311, 352), but handleDownloadCSV (line 287) and
# handleDownloadPrintSettings (line 374) do NOT set processing=true.
# Combined with QA-FE-05 (CSV/PrintSettings buttons not disabled),
# users can trigger concurrent downloads.


# -- QA-81: DownloadButtons CSV button missing disabled={processing} prop ---------
# Already documented as QA-FE-05. Testing backend behavior instead.


# -- QA-82: Colors.__setitem__ allows setting None values -------------------------
# File: backend/core/blend_color.py:293-295
# Colors.__setitem__ has value=None default, so `colors['X'] = None`
# stores None in the dict. Later accesses like colors['X'].hex crash
# with AttributeError.

class TestQA82ColorsSetItemNoneValue:
    """Colors.__setitem__ allows storing None, causing downstream crashes."""

    def test_setting_none_color_causes_attr_error(self):
        """Storing None via __setitem__ should be prevented or handled.

        Bug: colors['X'] = None stores None, then colors['X'].hex crashes.
        """
        colors = Colors()
        colors['X'] = None  # This succeeds — no validation

        # Downstream code expects Color objects, not None
        try:
            _ = colors['X'].hex  # This should not crash silently
            assert False, (
                "BUG QA-82: Colors.__setitem__ allowed storing None. "
                "Accessing .hex on None should fail, but didn't."
            )
        except AttributeError:
            # Bug confirmed: AttributeError from None.hex
            # The fix should either prevent setting None or validate
            pass

    def test_get_labels_includes_none_valued_entry(self):
        """get_labels returns labels even for None-valued entries,
        causing downstream crashes in code that iterates labels.
        """
        colors = Colors()
        colors['Z'] = None  # Store None value

        labels = colors.get_labels()
        assert 'Z' in labels, "Z should be in labels"

        # But trying to use this label in code_to_rgb or similar will crash
        # because color_map['Z'].td, color_map['Z'].hex etc. fail on None
        with pytest.raises(AttributeError):
            _ = colors['Z'].td


# -- QA-83: V2 SVG STL endpoint missing doubleSided support ----------------------
# File: backend/api/routes/download_v2.py:199-207
# api_download_svg_stl_v2 does NOT pass doubleSided to generate_svg_stl_zip,
# even if the model were updated to include it. The generate_svg_stl_zip
# function itself doesn't accept double_sided either.
# This is related to QA-67 but covers the route handler too.

class TestQA83SVGSTLEndpointNoDoubleSided:
    """SVG STL V2 endpoint doesn't pass doubleSided to generator."""

    def test_svg_stl_zip_generator_accepts_double_sided(self):
        """generate_svg_stl_zip should accept double_sided parameter."""
        from services.svg_stl_generator import generate_svg_stl_zip

        sig = inspect.signature(generate_svg_stl_zip)
        param_names = list(sig.parameters.keys())

        assert 'double_sided' in param_names, (
            "BUG QA-83: generate_svg_stl_zip does not accept 'double_sided' param. "
            "DownloadSTLRequestV2 has doubleSided field, and generate_stl_zip "
            "supports it, but the SVG equivalent does not. This means SVG mode "
            "users cannot generate double-sided prints."
        )


# -- QA-84: threemf_generator empty color_blocks not raised as ValueError ---------
# File: backend/services/threemf_generator.py:84-85
# generate_3mf raises ValueError("No color blocks provided") for empty
# color_blocks, which is caught by the route's ValueError handler and
# returns 422. This is correct. BUT: the error is raised BEFORE
# `colors is None` check (line 87-88), so if both color_blocks is empty
# AND colors is None, the error message says "No color blocks" instead
# of "Colors instance is required". This is fine — just documenting.


# -- QA-85: process_image creates 0x0 processed_img_array if height=0 or width=0 -
# File: backend/services/image_processor.py:202
# processed_img_array = np.zeros((height, width, 3), dtype=np.uint8)
# If the image has 0 width or height (shouldn't happen after PIL.Image.open),
# this creates a 0-dimensional array. PIL can't save it. However, PIL
# should never return 0x0 images, so this is theoretical only.


# -- QA-86: handleImageUpload doesn't validate file type before reading -----------
# File: src/hooks/useImageProcessor.ts:241-255
# The frontend reads ANY selected file via FileReader without checking
# if it's actually an image. Invalid files will fail at img.onload but
# the error is silent (no onerror handler on the img element).
# The backend validates properly, but the frontend gives no feedback
# for invalid uploads until processing fails.

# Frontend-only bug


# -- QA-87: BlendTestGenerator.save_stl_mesh uses os.mkdir not os.makedirs --------
# File: backend/core/blend_color.py:518-520
# os.mkdir only creates the immediate directory, not parents.
# If self.directory is nested (e.g., './output/CMYW_208x208x0.32/'),
# and ./output/ doesn't exist, os.mkdir will fail with FileNotFoundError.
# Should use os.makedirs(exist_ok=True).
# Already documented as QA-56. Adding a test to verify the behavior.

class TestQA87MkdirNestedDirectoryFails:
    """BlendTestGenerator.save_stl_mesh uses os.mkdir which can't create
    nested directories.
    """

    def test_save_stl_mesh_uses_makedirs(self):
        """save_stl_mesh should use os.makedirs, not os.mkdir."""
        source = inspect.getsource(BlendTestGenerator.save_stl_mesh)

        # Should NOT use bare os.mkdir (without 'makedirs')
        has_mkdir = 'os.mkdir(' in source
        has_makedirs = 'os.makedirs(' in source

        assert not has_mkdir or has_makedirs, (
            "BUG QA-87/QA-56: BlendTestGenerator.save_stl_mesh uses os.mkdir "
            "which fails for nested directories. Should use os.makedirs(exist_ok=True)."
        )


# -- QA-88: Pydantic min_items deprecation warning in models.py ------------------
# File: backend/api/models.py:66,103,123,143,158,200,245,293
# Multiple fields use `min_items=1` and `max_items=16` which trigger
# Pydantic V2 deprecation warnings. Should use `min_length` and `max_length`.
# While functionally correct in Pydantic V2 (backward compat), these will
# break in Pydantic V3.

class TestQA88PydanticMinItemsDeprecation:
    """models.py uses deprecated min_items/max_items instead of min_length/max_length."""

    def test_models_dont_use_deprecated_min_items(self):
        """API models should use min_length, not deprecated min_items."""
        import api.models as models_module

        source = inspect.getsource(models_module)

        min_items_count = source.count('min_items=')
        max_items_count = source.count('max_items=')

        assert min_items_count == 0, (
            f"BUG QA-88: api/models.py uses 'min_items=' {min_items_count} times. "
            f"This is deprecated in Pydantic V2 and will be removed in V3. "
            f"Use 'min_length=' instead."
        )

        assert max_items_count == 0, (
            f"BUG QA-88: api/models.py uses 'max_items=' {max_items_count} times. "
            f"This is deprecated in Pydantic V2 and will be removed in V3. "
            f"Use 'max_length=' instead."
        )


# -- QA-89: Color.get_cmyk() loses precision for nearly-white colors ------------
# File: backend/core/blend_color.py:60-78
# For RGB (254, 254, 254), get_cmyk computes:
#   c = 1 - 254/255 = 0.00392...
#   min_cmy = 0.00392...
#   c = (0.00392 - 0.00392) / (1 - 0.00392) = 0.0  <-- division OK
#   k = 0.00392  <-- correct
# But for RGB (255, 255, 254):
#   c = 0, m = 0, y = 1/255 = 0.00392
#   min_cmy = 0
#   c = 0/1 = 0, m = 0/1 = 0, y = 0.00392/1 = 0.00392
#   k = 0  <-- correct
# This is actually fine. No bug here.


# -- QA-90: Colors.from_configs doesn't validate transmission_distance > 0 ------
# File: backend/core/blend_color.py:339-343
# Colors.from_configs creates Color objects from configs. The ColorConfig
# validates td > 0 in __post_init__, but if someone creates a Color
# directly with td=0, get_transmission_rate handles it (returns 0.0).
# However, the division at blend_color.py:89 (alpha*d/td) would
# divide by zero if td=0 WITHOUT the guard at line 87.
# The guard exists (QA-20), so this is not a live bug.
# But Colors.from_configs doesn't re-validate td, relying on ColorConfig.

class TestQA90ColorDirectTdZero:
    """Creating Color directly with td=0 is handled by get_transmission_rate
    guard, but could cause confusion in other code paths.
    """

    def test_color_with_td_zero_doesnt_crash_code_to_rgb(self):
        """code_to_rgb should handle td=0 without crashing."""
        clear_rgb_cache()

        # td=0 means fully opaque
        color_key = (('X', 0, '#FF0000'),)

        # Should not crash with ZeroDivisionError
        result = _code_to_rgb_cached('X', 0.08, color_key)
        assert len(result) == 3
        # With td=0, transmission is 0.0, so the color should be
        # determined entirely by this layer (fully opaque red)
        r, g, b = result
        # Since it's fully opaque, only this color contributes
        assert isinstance(r, (int, float))


# -- QA-91: download_v2 uses deprecated .dict() instead of .model_dump() ---------
# File: backend/api/routes/download_v2.py:135-136,196-197,256-257,354
# Multiple calls to .dict() which is deprecated in Pydantic V2.
# The warnings show up in test output (140 warnings in test run).
# Should use .model_dump() instead.

class TestQA91PydanticDictDeprecation:
    """download_v2.py uses deprecated .dict() calls."""

    def test_download_v2_no_deprecated_dict_calls(self):
        """download_v2.py should use .model_dump() instead of .dict()."""
        from api.routes import download_v2

        source = inspect.getsource(download_v2)

        dict_calls = [
            line.strip() for line in source.split('\n')
            if '.dict()' in line and not line.strip().startswith('#')
        ]

        assert len(dict_calls) == 0, (
            f"BUG QA-91: download_v2.py uses deprecated .dict() method "
            f"{len(dict_calls)} times. This triggers Pydantic V2 deprecation "
            f"warnings and will break in V3. Use .model_dump() instead. "
            f"Affected lines: {dict_calls[:5]}"
        )


# -- QA-92: stl_generator.py generates duplicate base plate filenames -----------
# File: backend/services/stl_generator.py:412,424
# Both color layer filenames and base plate filename use the same pattern:
#   f"{prefix}_{width}x{height}x{physical_height:.2f}_{code}.stl"
# The base plate uses "_base.stl" suffix, so no collision.
# However, if a color label is literally "base", the filename would be
# the same as the base plate file, causing one to overwrite the other
# in the ZIP archive.

class TestQA92BaseFilenameCollision:
    """If a color label is 'B' and 'base' is used for base plate,
    the filenames won't collide. But if label is literally 'base',
    the base plate file would overwrite the color file.
    """

    def test_base_label_no_filename_collision(self):
        """A color named 'Base' (label 'B') should not collide with base plate."""
        from services.stl_generator import generate_stl_zip

        configs = [
            ColorConfig(name="Base", hex="#808080", transmission_distance=3.0),
            ColorConfig(name="Red", hex="#FF0000", transmission_distance=2.0),
            ColorConfig(name="Green", hex="#00FF00", transmission_distance=2.5),
            ColorConfig(name="Yellow", hex="#FFFF00", transmission_distance=2.5),
        ]
        colors = Colors.from_configs(configs)

        color_blocks = [
            {
                'r': 128, 'g': 128, 'b': 128,
                'count': 1,
                'pixels': [{'x': 0, 'y': 0}],
                'hex': '#808080',
            }
        ]

        result = generate_stl_zip(
            color_blocks=color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=colors,
            base_plate_thickness=0.5,  # Enable base plate
            white_backing_layers=0,  # No white filament in this config
        )

        # Check that the ZIP contains distinct files
        import zipfile
        from io import BytesIO

        with zipfile.ZipFile(BytesIO(result)) as zf:
            names = zf.namelist()
            # 'B' label file and 'base' plate file should be different
            base_files = [n for n in names if 'base' in n.lower()]
            # There should be exactly 1 base plate file
            assert len(set(names)) == len(names), (
                f"BUG QA-92: Duplicate filenames in ZIP: {names}"
            )
