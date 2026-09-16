"""
QA Round 14 bug tests.

Each test MUST FAIL while the bug is present. Tests are organized by bug ID.
"""
import os

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

# -- QA-153: SPA startswith path check has prefix collision -------------------
# File: backend/main.py:130
# `resolved_path.startswith(resolved_static)` matches /app/static_evil/foo.js

# -- QA-155: batch.py colorThreshold missing upper bound ----------------------
# File: backend/api/routes/batch.py:66,95
# colorThreshold=Form(50, ge=0) has no `le` upper bound.
# image.py has le=1000. Inconsistent validation.

# -- QA-157: batch.py pixelSize missing upper bound ---------------------------
# File: backend/api/routes/batch.py:67,96
# pixelSize=Form(0.08, gt=0) has no upper bound.

# -- QA-158: image.py pixelSize missing upper bound ----------------------------
# File: backend/api/routes/image.py:33
# pixelSize=Form(0.08, gt=0) has no upper bound. Same issue.



class TestRouteParamUpperBounds:
    """Form param upper bounds must reject oversized values (QA-155/157/158)."""

    @staticmethod
    def _locs(resp):
        return [e.get("loc", []) for e in resp.json().get("detail", [])]

    def test_batch_color_threshold_over_bound_rejected(self):
        from fastapi.testclient import TestClient
        from main import app

        resp = TestClient(app).post(
            "/api/batch/process", data={"colorThreshold": "5000"}
        )
        assert resp.status_code == 422
        assert any("colorThreshold" in loc for loc in self._locs(resp))

    def test_batch_pixel_size_over_bound_rejected(self):
        from fastapi.testclient import TestClient
        from main import app

        resp = TestClient(app).post("/api/batch/process", data={"pixelSize": "100"})
        assert resp.status_code == 422
        assert any("pixelSize" in loc for loc in self._locs(resp))

    def test_image_pixel_size_over_bound_rejected(self):
        from fastapi.testclient import TestClient
        from main import app

        resp = TestClient(app).post("/api/process-image", data={"pixelSize": "100"})
        assert resp.status_code == 422
        assert any("pixelSize" in loc for loc in self._locs(resp))
