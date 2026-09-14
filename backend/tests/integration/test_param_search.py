"""
Integration tests for POST /api/param-search and GET /api/param-search/progress/{job_id}.
"""
import io
import json

import pytest
from PIL import Image


def _make_png(size: int = 16) -> bytes:
    """Create a small multi-color PNG for testing."""
    img = Image.new("RGB", (size, size))
    pixels = img.load()
    half = size // 2
    for y in range(size):
        for x in range(size):
            if x < half and y < half:
                pixels[x, y] = (255, 0, 0)
            elif x >= half and y < half:
                pixels[x, y] = (0, 255, 0)
            elif x < half and y >= half:
                pixels[x, y] = (0, 0, 255)
            else:
                pixels[x, y] = (255, 255, 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Use a tiny grid so tests run fast: 2x2x1x1 = 4 combos
_TINY_RANGES = json.dumps({
    "max_colors": [6, 8],
    "color_threshold": [20, 40],
    "detail_size": [0.42],
    "white_backing_layers": [1],
})


@pytest.fixture
def png_bytes():
    return _make_png()


_FAST_FORM = {
    "preset": "bambu_cmyw_phase6",
    "mode": "pixel",
    "strategy": "random",
    "n_trials": "2",
    "seed": "42",
    "layer_count": "4",
    "layer_height": "0.08",
    "pixel_size": "0.42",
    "white_backing_layers": "1",
    "max_colors": "10",
    "color_threshold": "50",
    "detail_size": "0.42",
    "num_colors": "8",
    "epsilon": "2",
    "min_area": "4",
    "top_n": "2",
}


class TestParamSearchEndpoint:
    def test_returns_valid_response_structure(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data=_FAST_FORM,
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "job_id" in body
        assert "results" in body
        assert "total_evaluated" in body
        assert "elapsed_seconds" in body
        assert body["total_evaluated"] > 0

    def test_results_sorted_by_mae_ascending(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data={**_FAST_FORM, "n_trials": "3"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert len(results) > 0
        for i in range(len(results) - 1):
            assert results[i]["mae"] <= results[i + 1]["mae"], (
                f"Results not sorted: {results[i]['mae']} > {results[i+1]['mae']}"
            )

    def test_result_items_have_required_fields(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data=_FAST_FORM,
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        for item in resp.json()["results"]:
            assert "rank" in item
            assert "mode" in item
            assert "params" in item
            assert "mae" in item
            assert "preview_image" in item
            assert item["preview_image"].startswith("data:image/png;base64,")

    def test_invalid_preset_returns_400(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data={**_FAST_FORM, "preset": "nonexistent_preset_xyz"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 400

    def test_search_keeps_current_stack_and_includes_current_params(self, client, png_bytes):
        form = {
            **_FAST_FORM,
            "preset": "clear_cmyw",
            "layer_count": "8",
            "layer_height": "0.84",
            "white_backing_layers": "0",
            "max_colors": "50",
            "color_threshold": "35",
            "n_trials": "1",
        }
        resp = client.post(
            "/api/param-search",
            data=form,
            files={"image": ("test.png", png_bytes, "image/png")},
        )

        assert resp.status_code == 200, resp.text
        results = resp.json()["results"]
        assert any(
            item["params"]["max_colors"] == 50
            and item["params"]["color_threshold"] == 35
            and item["params"]["white_backing_layers"] == 0
            for item in results
        )

    def test_custom_filament_colors_run_search(self, client, png_bytes):
        """Custom color configs must be searchable, not just named presets."""
        colors = json.dumps([
            {"name": "C", "hex": "#00FFFF", "transmission_distance": 4.7},
            {"name": "M", "hex": "#FF00FF", "transmission_distance": 6.3},
            {"name": "Y", "hex": "#FFFF00", "transmission_distance": 10.1},
            {"name": "W", "hex": "#FFFFFF", "transmission_distance": 18.0},
        ])
        resp = client.post(
            "/api/param-search",
            data={
                **_FAST_FORM,
                "preset": None,
                "filamentColors": colors,
                "mode": "svg",
                "white_backing_layers": "0",
            },
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["results"]) > 0
        assert all(r["mode"] == "svg" for r in body["results"])

    def test_rate_limit_third_request_returns_429(self, client, png_bytes):
        """Third request within 1 minute should be rate-limited."""
        fast_form = {**_FAST_FORM, "n_trials": "1"}
        for _ in range(2):
            resp = client.post(
                "/api/param-search",
                data=fast_form,
                files={"image": ("test.png", png_bytes, "image/png")},
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"

        resp = client.post(
            "/api/param-search",
            data=fast_form,
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 429


class TestParamSearchProgressEndpoint:
    def test_unknown_job_id_returns_404(self, client):
        resp = client.get("/api/param-search/progress/nonexistent-job-id-xyz")
        assert resp.status_code == 404

    def test_progress_endpoint_streams_complete_event(self, client, png_bytes):
        """After a search completes, the SSE stream should contain a 'complete' event."""
        resp = client.post(
            "/api/param-search",
            data={**_FAST_FORM, "n_trials": "1"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        sse_resp = client.get(f"/api/param-search/progress/{job_id}")
        assert sse_resp.status_code == 200
        assert "text/event-stream" in sse_resp.headers.get("content-type", "")

        events = []
        for line in sse_resp.text.splitlines():
            if line.startswith("data: "):
                try:
                    events.append(json.loads(line[6:]))
                except json.JSONDecodeError:
                    pass

        statuses = [e.get("status") for e in events]
        assert "complete" in statuses, f"Expected 'complete' status in events, got: {statuses}"
