"""
Integration tests for POST /api/param-search and GET /api/param-search/progress/{job_id}.
"""
import io
import json
import threading
import time

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


@pytest.fixture
def png_bytes():
    return _make_png()


_FAST_FORM = {
    "preset": "bambu_cmyw",
    "mode": "pixel",
    "n_trials": "2",
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
}


def _wait_for_job(client, job_id: str, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/param-search/progress/{job_id}")
        assert response.status_code == 200, response.text
        snapshot = response.json()
        if snapshot["status"] != "running":
            return snapshot
        time.sleep(0.01)
    pytest.fail(f"Search job {job_id} did not finish in {timeout}s")


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
        assert body["status"] in ("running", "complete")
        assert body["total"] == 3
        assert "results" in body
        finished = _wait_for_job(client, body["job_id"])
        assert finished["status"] == "complete"
        assert finished["completed"] == finished["total"] == 3

    def test_results_keep_evaluation_order_and_label_current_settings(self, client, png_bytes):
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "3"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        results = _wait_for_job(client, resp.json()["job_id"])["results"]
        assert [item["candidate_id"] for item in results] == [1, 2, 3, 4]
        assert [item["is_baseline"] for item in results] == [True, False, False, False]
        # The current settings, then the search's coarse lattice in order.
        assert [item["params"] for item in results] == [
            {"max_colors": colors, "color_threshold": threshold, "detail_size": 0.42, "white_backing_layers": 1}
            for colors, threshold in [(10, 50), (6, 10), (6, 15), (6, 40)]
        ]

    def test_result_items_have_required_fields(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data=_FAST_FORM,
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200, resp.text
        for item in _wait_for_job(client, resp.json()["job_id"])["results"]:
            assert "candidate_id" in item
            assert "is_baseline" in item
            assert "mode" in item
            assert "params" in item
            assert isinstance(item["score"], float) and item["score"] >= 0
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
        results = _wait_for_job(client, resp.json()["job_id"])["results"]
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
        body = _wait_for_job(client, resp.json()["job_id"])
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
            client.delete(f"/api/param-search/progress/{resp.json()['job_id']}")
            deadline = time.monotonic() + 10
            while not client.get("/api/param-search/availability").json()["available"]:
                assert time.monotonic() < deadline
                time.sleep(0.02)

        resp = client.post(
            "/api/param-search",
            data=fast_form,
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) > 0
        assert resp.json() == {"detail": "Rate limit exceeded: 2 per 1 minute"}


class TestParamSearchProgressEndpoint:
    def test_unknown_job_id_returns_404(self, client):
        resp = client.get("/api/param-search/progress/nonexistent-job-id-xyz")
        assert resp.status_code == 404

    def test_progress_returns_only_new_completed_previews(self, client, png_bytes):
        resp = client.post(
            "/api/param-search",
            data={**_FAST_FORM, "n_trials": "1"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        finished = _wait_for_job(client, job_id)
        assert finished["status"] == "complete"
        assert [item["candidate_id"] for item in finished["results"]] == [1, 2]

        delta = client.get(f"/api/param-search/progress/{job_id}?after=1")
        assert delta.status_code == 200
        assert delta.json()["completed"] == 2
        assert [item["candidate_id"] for item in delta.json()["results"]] == [2]
        assert client.get(f"/api/param-search/progress/{job_id}?after=-1").status_code == 422

    def test_slow_first_candidate_does_not_block_start_or_report_zero_results(
        self, client, png_bytes, monkeypatch,
    ):
        from services.param_search_service import Evaluator, SearchResult
        started = threading.Event()
        release = threading.Event()

        def slow_evaluate(self, params, mode):
            started.set()
            assert release.wait(timeout=5)
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", slow_evaluate)
        try:
            started_at = time.monotonic()
            resp = client.post(
                "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
                files={"image": ("test.png", png_bytes, "image/png")},
            )
            assert resp.status_code == 200, resp.text
            assert time.monotonic() - started_at < 1.0
            assert started.wait(timeout=2)
            job_id = resp.json()["job_id"]
            pending = client.get(f"/api/param-search/progress/{job_id}").json()
            assert pending["status"] == "running"
            assert pending["completed"] == 0
            assert pending["results"] == []
        finally:
            release.set()
        assert _wait_for_job(client, job_id)["completed"] == 2

    def test_cancel_discards_inflight_candidate(self, client, png_bytes, monkeypatch):
        from services.param_search_service import Evaluator, SearchResult
        started = threading.Event()
        release = threading.Event()

        def slow_evaluate(self, params, mode):
            started.set()
            assert release.wait(timeout=5)
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", slow_evaluate)
        try:
            resp = client.post(
                "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
                files={"image": ("test.png", png_bytes, "image/png")},
            )
            job_id = resp.json()["job_id"]
            assert started.wait(timeout=2)
            cancelled = client.delete(f"/api/param-search/progress/{job_id}")
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
        finally:
            release.set()
        assert _wait_for_job(client, job_id)["results"] == []

    def test_worker_error_is_visible_in_job_snapshot(self, client, png_bytes, monkeypatch):
        from services.param_search_service import Evaluator

        def fail(self, params, mode):
            raise ValueError("candidate renderer failed")

        monkeypatch.setattr(Evaluator, "evaluate", fail)
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        finished = _wait_for_job(client, resp.json()["job_id"])
        assert finished["status"] == "error"
        assert "candidate renderer failed" in finished["error"]
        assert "0 of 2 previews completed" in finished["error"]
        assert finished["completed"] == 0

    def test_invalid_candidate_keeps_later_previews(self, client, png_bytes, monkeypatch):
        from services.param_search_service import Evaluator, SearchResult

        attempts = []

        def evaluate(self, params, mode):
            attempts.append(1)
            if len(attempts) == 2:
                raise ValueError("Too many colors for this image")
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", evaluate)
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "2"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        finished = _wait_for_job(client, resp.json()["job_id"])
        assert finished["status"] == "error"
        assert finished["settled"] is True
        assert finished["completed"] == 2
        assert [item["candidate_id"] for item in finished["results"]] == [1, 3]
        assert "2 of 3 previews completed" in finished["error"]
        assert "option 2: Too many colors for this image" in finished["error"]

    def test_budget_exhausted_before_first_preview_has_explicit_error(
        self, client, png_bytes, monkeypatch,
    ):
        from api.routes import param_search
        monkeypatch.setattr(param_search.settings, "param_search_job_budget_seconds", 0.0)
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        finished = _wait_for_job(client, resp.json()["job_id"])
        assert finished["status"] == "error"
        assert finished["error"] == "Search stopped after 0s; 0 of 2 previews completed."
        assert finished["completed"] == 0

    def test_budget_exhausted_after_first_preview_retains_partial_result(
        self, client, png_bytes, monkeypatch,
    ):
        from api.routes import param_search
        from services.param_search_service import Evaluator, SearchResult

        monkeypatch.setattr(param_search.settings, "param_search_job_budget_seconds", 0.05)

        def slow_evaluate(self, params, mode):
            time.sleep(0.06)
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", slow_evaluate)
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        finished = _wait_for_job(client, resp.json()["job_id"])
        assert finished["status"] == "error"
        assert finished["error"] == "Search stopped after 0.05s; 1 of 2 previews completed."
        assert finished["completed"] == 1
        assert [item["candidate_id"] for item in finished["results"]] == [1]

    def test_job_abandoned_by_its_page_frees_the_search_slot(
        self, client, png_bytes, monkeypatch,
    ):
        from api.routes import param_search
        from services.param_search_service import Evaluator, SearchResult

        monkeypatch.setattr(param_search.settings, "param_search_abandon_seconds", 0.05)

        def slow_evaluate(self, params, mode):
            time.sleep(0.1)
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", slow_evaluate)
        resp = client.post(
            "/api/param-search", data={**_FAST_FORM, "n_trials": "5"},
            files={"image": ("test.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 200
        deadline = time.monotonic() + 5
        while not client.get("/api/param-search/availability").json()["available"]:
            assert time.monotonic() < deadline, "abandoned job kept the search slot"
            time.sleep(0.05)
        snapshot = client.get(f"/api/param-search/progress/{resp.json()['job_id']}").json()
        assert snapshot["status"] == "cancelled"
        assert snapshot["completed"] == 1

    def test_single_flight_rejects_overlap_until_cancelled_worker_exits(
        self, client, png_bytes, monkeypatch,
    ):
        from api.rate_limiter import limiter
        from api.routes import param_search
        from services.param_search_service import Evaluator, SearchResult

        monkeypatch.setattr(limiter, "enabled", False)
        started = threading.Event()
        release = threading.Event()
        calls = []

        def blocked_once(self, params, mode):
            calls.append(1)
            if len(calls) == 1:
                started.set()
                assert release.wait(timeout=5)
            return SearchResult(0, False, mode, dict(params), "data:image/png;base64,eA==", 1.0)

        monkeypatch.setattr(Evaluator, "evaluate", blocked_once)

        def start_job():
            return client.post(
                "/api/param-search", data={**_FAST_FORM, "n_trials": "1"},
                files={"image": ("test.png", png_bytes, "image/png")},
            )

        try:
            first = start_job()
            assert first.status_code == 200, first.text
            job_id = first.json()["job_id"]
            assert started.wait(timeout=2)

            overlap = start_job()
            assert overlap.status_code == 503
            assert "already running" in overlap.json()["detail"]
            assert client.get(f"/api/param-search/progress/{job_id}").json()["completed"] == 0

            cancelled = client.delete(f"/api/param-search/progress/{job_id}")
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
            assert cancelled.json()["settled"] is False
            assert start_job().status_code == 503  # In-flight candidate still uses the worker.
            assert client.get("/api/param-search/availability").json() == {"available": False}
        finally:
            release.set()

        deadline = time.monotonic() + 2
        while param_search._job_store.get(job_id).finished_at is None:
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert client.get(f"/api/param-search/progress/{job_id}").json()["results"] == []
        assert client.get(f"/api/param-search/progress/{job_id}").json()["settled"] is True
        assert client.get("/api/param-search/availability").json() == {"available": True}

        next_job = start_job()
        assert next_job.status_code == 200, next_job.text
        assert _wait_for_job(client, next_job.json()["job_id"])["status"] == "complete"

    def test_cancelled_terminal_job_is_evicted_after_ttl(self):
        from api.routes.param_search import SearchJobStore

        store = SearchJobStore()
        job = store.create(total=2)
        job.cancel()
        assert job.finished_at is None  # Worker still owns its slot.
        job.finish()
        assert job.finished_at is not None
        job.finished_at -= store._TTL + 1
        assert store.get(job.job_id) is None


@pytest.mark.parametrize("mode", ["pixel", "svg"])
def test_search_preview_matches_applying_same_settings(client, mode):
    """A full-size RGBA image exercises the old resize/alpha/cleanup divergence."""
    image = Image.new("RGBA", (513, 73), (20, 50, 180, 255))
    for x in range(40, 450):
        for y in range(10, 55):
            image.putpixel((x, y), (190, 20, 40, 0 if x % 7 == 0 else 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    form = {**_FAST_FORM, "mode": mode, "n_trials": "1", "detail_size": "0.6", "white_backing_layers": "3"}
    search = client.post(
        "/api/param-search", data=form,
        files={"image": ("preview.png", png_bytes, "image/png")},
    )
    assert search.status_code == 200, search.text
    baseline = _wait_for_job(client, search.json()["job_id"])["results"][0]
    assert baseline["is_baseline"]
    applied = client.post(
        "/api/process-image",
        data={
            "mode": mode, "filamentPreset": form["preset"],
            "layerCount": form["layer_count"], "layerHeight": form["layer_height"],
            "whiteBackingLayers": form["white_backing_layers"], "pixelSize": form["pixel_size"],
            "maxColors": form["max_colors"], "colorThreshold": form["color_threshold"],
            "detailSize": form["detail_size"], "numColors": form["num_colors"],
            "epsilon": form["epsilon"], "minArea": form["min_area"],
        },
        files={"image": ("preview.png", png_bytes, "image/png")},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["imageDimensions"] == {"width": 513, "height": 73}
    assert applied.json()["processedImage"] == baseline["preview_image"]
