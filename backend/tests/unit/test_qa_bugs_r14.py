"""
QA Round 14 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import ast
import os
import re

import pytest

from services.analytics import AnalyticsCollector


# -- QA-149: getErrorDetail returns array for FastAPI validation errors --------
# File: src/api/client.ts:26-33
# getErrorDetail does `body.detail || fallback`. FastAPI validation errors return
# detail as an ARRAY of objects [{type, loc, msg, ...}], not a string.
# `new Error(array)` produces message "[object Object]" displayed in the UI.
# Frontend-only bug — tested via source inspection below.

class TestQA149GetErrorDetailArrayHandling:
    """getErrorDetail should handle array-format detail from FastAPI validation."""

    def test_get_error_detail_handles_array_detail(self):
        """getErrorDetail should extract message from array detail, not return raw array."""
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "src", "api", "client.ts"
        )
        with open(src_path) as f:
            source = f.read()

        # FastAPI validation errors return: {"detail": [{type, loc, msg, ...}, ...]}
        # The current code does: body.detail || fallback
        # When detail is an array, this returns the array (truthy), not a string.
        # new Error(array) => Error with message "[object Object]"
        #
        # Fix: should check if detail is a string first, or extract msg from array
        has_array_handling = (
            "Array.isArray" in source or
            "typeof body.detail === 'string'" in source or
            "typeof detail === 'string'" in source or
            ".detail?.map" in source or
            "detail[0]" in source
        )

        assert has_array_handling, (
            "BUG QA-149: getErrorDetail in client.ts does `body.detail || fallback` "
            "but FastAPI validation errors return detail as an ARRAY of objects, not "
            "a string. `new Error(array)` produces message '[object Object]'. "
            "Fix: check if detail is an array and extract the message(s)."
        )


# -- QA-150: FilamentPreview sends both filamentPreset AND filamentColors ------
# File: src/components/FilamentPreview.tsx:59-65
# The component always passes filamentPreset AND filamentColors to the API.
# The backend root_validator rejects this with 422 ("Cannot provide both").
# The error message shows as "[object Object]" on every page load.

class TestQA150FilamentPreviewSendsBoth:
    """FilamentPreview must not send both filamentPreset and filamentColors."""

    def test_frontend_preview_should_not_send_both(self):
        """FilamentPreview.tsx should only send one of preset or colors."""
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "src",
            "components", "FilamentPreview.tsx"
        )
        with open(src_path) as f:
            source = f.read()

        has_unconditional_both = (
            "filamentPreset: filamentPreset ?? undefined" in source and
            "filamentColors," in source
        )

        assert not has_unconditional_both, (
            "BUG QA-150: FilamentPreview.tsx sends BOTH filamentPreset AND "
            "filamentColors to /api/filament-preview. The backend root_validator "
            "rejects with 422, causing '[object Object]' error on every page load."
        )


# -- QA-151: Analytics KNOWN_ENDPOINTS missing V2 paths -----------------------
# File: backend/services/analytics.py:29-42
# KNOWN_ENDPOINTS lacks all /api/v2/* paths. These get normalized to
# /api/{unknown}, making V2 endpoint analytics completely useless.

class TestQA151AnalyticsV2EndpointsMissing:
    """V2 API endpoints should be tracked individually, not as {unknown}."""

    V2_ENDPOINTS = [
        "/api/v2/download-stl",
        "/api/v2/download-svg-stl",
        "/api/v2/download-3mf",
        "/api/v2/print-settings",
        "/api/v2/filament-presets",
    ]

    @pytest.mark.parametrize("path", V2_ENDPOINTS)
    def test_v2_endpoint_not_normalized_to_unknown(self, path):
        """V2 endpoint should NOT be normalized to /api/{unknown}."""
        normalized = AnalyticsCollector._normalize_path(path)
        assert normalized != "/api/{unknown}", (
            f"BUG QA-151: V2 endpoint '{path}' is normalized to '/api/{{unknown}}'. "
            f"Add V2 endpoints to KNOWN_ENDPOINTS in analytics.py."
        )

    def test_v2_endpoints_in_known_set(self):
        """V2 endpoints should be in KNOWN_ENDPOINTS."""
        known = AnalyticsCollector.KNOWN_ENDPOINTS
        missing = [p for p in self.V2_ENDPOINTS if p not in known]
        assert not missing, (
            f"BUG QA-151: V2 endpoints missing from KNOWN_ENDPOINTS: {missing}"
        )


# -- QA-152: health.py dead imports ------------------------------------------
# File: backend/api/routes/health.py:4-5
# `import platform` and `import sys` are unused after removing version info.

class TestQA152HealthDeadImports:
    """health.py should not import unused modules."""

    def test_no_dead_imports(self):
        """health.py should not import 'platform' or 'sys' if they're unused."""
        health_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "api", "routes", "health.py"
        )
        with open(health_path) as f:
            source = f.read()

        tree = ast.parse(source)
        imported_names = set()
        used_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                pass
            elif isinstance(node, ast.Name):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)

        dead = [name for name in ["platform", "sys"]
                if name in imported_names and name not in used_names]

        assert not dead, (
            f"BUG QA-152: health.py imports unused modules: {dead}. "
            f"Remove dead imports."
        )


# -- QA-153: SPA startswith path check has prefix collision -------------------
# File: backend/main.py:130
# `resolved_path.startswith(resolved_static)` matches /app/static_evil/foo.js

class TestQA153SPAStartswithPrefixCollision:
    """SPA path check should use os.sep suffix to prevent prefix collisions."""

    def test_startswith_with_sep_suffix(self):
        """serve_spa path validation should append os.sep to prevent prefix collision."""
        main_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "main.py"
        )
        with open(main_path) as f:
            source = f.read()

        has_sep_check = (
            "startswith(resolved_static + os.sep)" in source or
            'startswith(resolved_static + "/")' in source or
            "startswith(resolved_static + os.path.sep)" in source or
            ("resolved_path == resolved_static" in source and
             "startswith(resolved_static" in source)
        )

        assert has_sep_check, (
            "BUG QA-153: SPA serve_spa route uses "
            "`startswith(resolved_static)` without os.sep suffix. "
            "'/app/static_evil/file.js' would pass when static_dir is '/app/static'."
        )


# -- QA-155: batch.py colorThreshold missing upper bound ----------------------
# File: backend/api/routes/batch.py:66,95
# colorThreshold=Form(50, ge=0) has no `le` upper bound.
# image.py has le=1000. Inconsistent validation.

class TestQA155BatchColorThresholdNoUpperBound:
    """batch.py colorThreshold should have le upper bound like image.py."""

    def test_batch_routes_have_threshold_upper_bound(self):
        """All batch route colorThreshold params should have le constraint."""
        batch_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "api", "routes", "batch.py"
        )
        with open(batch_path) as f:
            source = f.read()

        threshold_forms = re.findall(
            r'colorThreshold.*?Form\((.*?)\)', source
        )

        assert len(threshold_forms) > 0, "No colorThreshold Form params found"

        missing_le = [form for form in threshold_forms if "le=" not in form]

        assert not missing_le, (
            f"BUG QA-155: batch.py colorThreshold Form params lack 'le' upper bound. "
            f"Found: {threshold_forms}. "
            f"image.py enforces le=1000. Add le=1000 to batch route params."
        )


# -- QA-157: batch.py pixelSize missing upper bound ---------------------------
# File: backend/api/routes/batch.py:67,96
# pixelSize=Form(0.08, gt=0) has no upper bound.

class TestQA157BatchPixelSizeNoUpperBound:
    """batch.py pixelSize should have le upper bound."""

    def test_batch_routes_have_pixelsize_upper_bound(self):
        """All batch route pixelSize params should have le constraint."""
        batch_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "api", "routes", "batch.py"
        )
        with open(batch_path) as f:
            source = f.read()

        pixelsize_forms = re.findall(
            r'pixelSize.*?Form\((.*?)\)', source
        )

        assert len(pixelsize_forms) > 0, "No pixelSize Form params found"

        missing_le = [form for form in pixelsize_forms if "le=" not in form]

        assert not missing_le, (
            f"BUG QA-157: batch.py pixelSize Form params lack 'le' upper bound. "
            f"Found: {pixelsize_forms}. "
            f"A client can send pixelSize=1000000 causing excessively large output."
        )


# -- QA-158: image.py pixelSize missing upper bound ----------------------------
# File: backend/api/routes/image.py:33
# pixelSize=Form(0.08, gt=0) has no upper bound. Same issue.

class TestQA158ImagePixelSizeNoUpperBound:
    """image.py pixelSize should have le upper bound."""

    def test_image_route_has_pixelsize_upper_bound(self):
        """Image route pixelSize param should have le constraint."""
        image_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "api", "routes", "image.py"
        )
        with open(image_path) as f:
            source = f.read()

        pixelsize_forms = re.findall(
            r'pixelSize.*?Form\((.*?)\)', source
        )

        assert len(pixelsize_forms) > 0, "No pixelSize Form params found"

        missing_le = [form for form in pixelsize_forms if "le=" not in form]

        assert not missing_le, (
            f"BUG QA-158: image.py pixelSize Form param lacks 'le' upper bound. "
            f"Found: {pixelsize_forms}. "
            f"A client can send pixelSize=1000000. Add a reasonable le constraint."
        )
