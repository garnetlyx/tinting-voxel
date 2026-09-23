"""Parameter alternatives preserve the apply pipeline and generation order."""
import base64
import io
import threading
import time

import pytest
from PIL import Image

from core.color_config import get_preset
from core.color_materials import Colors
from services.param_search_service import Evaluator, FixedParams, ParamSearchConfig, ParamSearchService, SearchResult

FIXED = FixedParams(layer_count=4, layer_height=0.08, pixel_size=0.42, white_backing_layers=3)
RANGES = {"max_colors": [8, 4, 12], "color_threshold": [40], "detail_size": [0.6]}


@pytest.fixture
def colors():
    return Colors.from_configs(get_preset("bambu_cmyw_phase6"))


@pytest.fixture
def png_bytes():
    image = Image.new("RGBA", (513, 73), (32, 70, 180, 255))
    for x in range(60, 440):
        for y in range(10, 55):
            image.putpixel((x, y), (180, 30, 50, 0 if x % 7 == 0 else 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def service(colors, baseline=None):
    return ParamSearchService(ParamSearchConfig(
        mode="pixel", strategy="grid", n_trials=3, seed=7,
        fixed=FIXED, colors=colors, param_ranges=RANGES,
        baseline_params={"pixel": baseline} if baseline else None,
    ))


def fake_evaluate(self, params, mode):
    return SearchResult(0, False, mode, dict(params), "data:image/png;base64,")


def test_pixel_pipeline_receives_original_bytes_and_physical_parameters(png_bytes, colors, monkeypatch):
    captured = {}

    def process(**kwargs):
        captured.update(kwargs)
        return {"processedImage": "preview"}

    monkeypatch.setattr("services.image_processor.process_image", process)
    evaluator = Evaluator(png_bytes, colors, FIXED)
    result = evaluator.evaluate({"max_colors": 4, "color_threshold": 16.5, "detail_size": 0.54}, "pixel")
    assert captured["image_bytes"] == png_bytes
    assert captured["pixel_size"] == FIXED.pixel_size
    assert captured["layer_height"] == FIXED.layer_height
    assert captured["white_backing_layers"] == FIXED.white_backing_layers
    assert captured["detail_size"] == 0.54
    assert result.preview_data_url == "preview"


def test_pixel_preview_equals_direct_application(png_bytes, colors):
    from services.image_processor import process_image
    params = {"max_colors": 4, "color_threshold": 16.5, "detail_size": 0.54}
    result = Evaluator(png_bytes, colors, FIXED).evaluate(params, "pixel")
    applied = process_image(
        image_bytes=png_bytes, filament_colors=colors,
        layer_count=FIXED.layer_count, layer_height=FIXED.layer_height,
        pixel_size=FIXED.pixel_size, white_backing_layers=FIXED.white_backing_layers,
        **params,
    )
    assert result.preview_data_url == applied["processedImage"]
    image = Image.open(io.BytesIO(base64.b64decode(result.preview_data_url.split(",", 1)[1])))
    assert image.size == (513, 73)


def test_candidates_remain_in_generation_order(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", fake_evaluate)
    results = service(colors).run(b"image")
    assert [r.params["max_colors"] for r in results] == [8, 4, 12]
    assert [r.candidate_id for r in results] == [1, 2, 3]
    assert not any(r.is_baseline for r in results)
    assert all(not hasattr(r, "mae") and not hasattr(r, "rank") for r in results)


def test_current_settings_are_first_and_not_duplicated(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", fake_evaluate)
    baseline = {"max_colors": 4, "color_threshold": 40, "detail_size": 0.6}
    results = service(colors, baseline).run(b"image")
    assert [r.params["max_colors"] for r in results] == [4, 8, 12]
    assert [r.is_baseline for r in results] == [True, False, False]
    assert baseline == {"max_colors": 4, "color_threshold": 40, "detail_size": 0.6}


def test_cancellation_stops_between_candidates(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", fake_evaluate)
    cancel = threading.Event()
    events = []

    def on_result(result):
        events.append(result)
        cancel.set()

    results = service(colors).run(b"image", on_result=on_result, cancel=cancel)
    assert len(results) == 1
    assert events[0].candidate_id == 1


def test_budget_stops_between_candidates_after_preserving_first_preview(colors, monkeypatch):
    calls = []

    def evaluate(self, params, mode):
        calls.append(params["max_colors"])
        time.sleep(0.02)
        return fake_evaluate(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    results = service(colors).run(b"image", budget_seconds=0.01)
    assert [r.params["max_colors"] for r in results] == [8]
    assert calls == [8]


def test_invalid_candidate_is_recorded_and_later_candidates_render(colors, monkeypatch):
    def evaluate(self, params, mode):
        if params["max_colors"] == 4:
            raise ValueError("Invalid candidate")
        return fake_evaluate(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    failures = []
    results = service(colors).run(b"image", on_candidate_error=lambda candidate_id, reason: failures.append((candidate_id, reason)))
    assert [result.candidate_id for result in results] == [1, 3]
    assert failures == [(2, "Invalid candidate")]


def test_unexpected_renderer_failure_remains_fail_stop(colors, monkeypatch):
    def evaluate(self, params, mode):
        if params["max_colors"] == 4:
            raise RuntimeError("Renderer unavailable")
        return fake_evaluate(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    completed = []
    with pytest.raises(RuntimeError, match="Renderer unavailable"):
        service(colors).run(b"image", on_result=completed.append)
    assert [result.candidate_id for result in completed] == [1]
