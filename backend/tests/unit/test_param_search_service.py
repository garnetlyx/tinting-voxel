"""The search renders candidates as applying them would, scores them against the
image, and visits the grid in pattern-search order."""
import base64
import io
import itertools
import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

from config.settings import settings
from core.color_config import get_preset
from core.color_materials import Colors
from services.param_search_service import (
    SEARCH_SPACES,
    Evaluator,
    FixedParams,
    ParamSearchConfig,
    ParamSearchService,
    PatternSearch,
    SearchResult,
    SearchSpace,
)

FIXED = FixedParams(layer_count=4, layer_height=0.08, pixel_size=0.42, white_backing_layers=3, detail_size=0.6)
SPACE = SearchSpace(
    axes={"max_colors": (4, 8, 12), "color_threshold": (20, 40)},
    coarse={"max_colors": (8,), "color_threshold": (40,)},
)
# Mean CIEDE2000 at every grid point of each mode, recorded for real images and
# filament sets, with the app's default settings as the starting point.
LANDSCAPES = json.loads((Path(__file__).parent.parent / "fixtures" / "search_landscapes.json").read_text())


@pytest.fixture
def colors():
    return Colors.from_configs(get_preset("bambu_cmyw"))


@pytest.fixture
def png_bytes():
    image = Image.new("RGBA", (513, 73), (32, 70, 180, 255))
    for x in range(60, 440):
        for y in range(10, 55):
            image.putpixel((x, y), (180, 30, 50, 0 if x % 7 == 0 else 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def service(colors, baseline, n_trials=3):
    return ParamSearchService(ParamSearchConfig(
        mode="pixel", n_trials=n_trials, fixed=FIXED, colors=colors,
        baseline_params=baseline, space=SPACE,
    ))


def scored_by(score):
    def evaluate(self, params, mode):
        return SearchResult(0, False, mode, dict(params), "data:image/png;base64,", score(params))
    return evaluate


def decode(data_url):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB"))


def test_pixel_pipeline_receives_original_bytes_and_physical_parameters(png_bytes, colors, monkeypatch):
    from services import image_processor
    captured = {}
    process_image = image_processor.process_image

    def process(**kwargs):
        captured.update(kwargs)
        return process_image(**kwargs)

    monkeypatch.setattr(image_processor, "process_image", process)
    Evaluator(png_bytes, colors, FIXED).evaluate({"max_colors": 4, "color_threshold": 16.5}, "pixel")
    assert captured["image_bytes"] == png_bytes
    assert captured["pixel_size"] == FIXED.pixel_size
    assert captured["layer_height"] == FIXED.layer_height
    assert captured["white_backing_layers"] == FIXED.white_backing_layers
    assert captured["detail_size"] == FIXED.detail_size


def test_pixel_preview_equals_direct_application(png_bytes, colors):
    from services.image_processor import process_image
    params = {"max_colors": 4, "color_threshold": 16.5}
    result = Evaluator(png_bytes, colors, FIXED).evaluate(params, "pixel")
    applied = process_image(
        image_bytes=png_bytes, filament_colors=colors,
        layer_count=FIXED.layer_count, layer_height=FIXED.layer_height,
        pixel_size=FIXED.pixel_size, white_backing_layers=FIXED.white_backing_layers,
        detail_size=FIXED.detail_size, **params,
    )
    assert result.preview_data_url == applied["processedImage"]
    assert decode(result.preview_data_url).shape == (73, 513, 3)


@pytest.mark.parametrize("mode, params", [
    ("pixel", {"max_colors": 4, "color_threshold": 16.5}),
    ("svg", {"num_colors": 4, "epsilon": 2.0, "min_area": 4.0}),
])
def test_score_is_mean_ciede2000_from_the_image_on_the_model_grid(png_bytes, colors, mode, params):
    result = Evaluator(png_bytes, colors, FIXED).evaluate(params, mode)
    # Transparent pixels print as the white base.
    rgba = Image.open(io.BytesIO(png_bytes))
    image = Image.new("RGB", rgba.size, (255, 255, 255))
    image.paste(rgba, mask=rgba.split()[3])
    image = np.asarray(image)
    preview = decode(result.preview_data_url)
    assert preview.shape == image.shape
    expected = deltaE_ciede2000(rgb2lab(image), rgb2lab(preview), channel_axis=-1).mean()
    assert result.score == pytest.approx(expected, rel=1e-9)


def test_current_settings_come_first_and_are_not_repeated(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", scored_by(lambda params: 1.0))
    results = service(colors, {"max_colors": 8, "color_threshold": 40}).run(b"image")
    assert [r.params["max_colors"] for r in results] == [8, 12, 4, 8]
    assert [r.params["color_threshold"] for r in results] == [40, 40, 40, 20]
    assert [r.is_baseline for r in results] == [True, False, False, False]
    assert [r.candidate_id for r in results] == [1, 2, 3, 4]
    assert all(r.params["detail_size"] == 0.6 and r.params["white_backing_layers"] == 3 for r in results)


def test_off_grid_current_settings_are_scored_without_steering_the_search(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", scored_by(lambda params: 0.0 if params["color_threshold"] == 33 else 1.0))
    search = service(colors, {"max_colors": 8, "color_threshold": 33})
    assert search.total_candidates() == 4
    results = search.run(b"image")
    assert [(r.params["max_colors"], r.params["color_threshold"]) for r in results] == [(8, 33), (8, 40), (12, 40), (4, 40)]
    assert [r.score for r in results] == [0.0, 1.0, 1.0, 1.0]


def test_parameters_outside_the_space_keep_the_current_values(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", scored_by(lambda params: 1.0))
    results = service(colors, {"max_colors": 8, "color_threshold": 40, "extra": 7}).run(b"image")
    assert all(r.params["extra"] == 7 for r in results)
    assert [r.params["max_colors"] for r in results] == [8, 12, 4, 8]


def test_total_counts_the_current_settings_and_stops_at_the_grid_size(colors):
    assert service(colors, {"max_colors": 8, "color_threshold": 40}, n_trials=3).total_candidates() == 4
    assert service(colors, {"max_colors": 8, "color_threshold": 40}, n_trials=50).total_candidates() == 6
    assert service(colors, {"max_colors": 9, "color_threshold": 40}, n_trials=50).total_candidates() == 7


def test_pattern_search_descends_to_the_minimum_without_visiting_the_whole_grid():
    search = PatternSearch(SearchSpace(
        axes={"a": tuple(range(1, 10)), "b": tuple(range(1, 10))},
        coarse={"a": (2, 5, 8), "b": (2, 5, 8)},
    ))
    visited = []
    for _ in range(17):
        params = search.next()
        search.record(params, (params["a"] - 7) ** 2 + (params["b"] - 3) ** 2)
        visited.append((params["a"], params["b"]))
    assert (7, 3) in visited
    assert len(set(visited)) == 17 < 81


def test_cancellation_stops_between_candidates(colors, monkeypatch):
    monkeypatch.setattr(Evaluator, "evaluate", scored_by(lambda params: 1.0))
    cancel = threading.Event()
    events = []

    def on_result(result):
        events.append(result)
        cancel.set()

    results = service(colors, {"max_colors": 8, "color_threshold": 40}).run(b"image", on_result=on_result, cancel=cancel)
    assert len(results) == 1
    assert events[0].candidate_id == 1


def test_budget_stops_between_candidates_after_preserving_first_preview(colors, monkeypatch):
    calls = []

    def evaluate(self, params, mode):
        calls.append(params["max_colors"])
        time.sleep(0.02)
        return scored_by(lambda params: 1.0)(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    results = service(colors, {"max_colors": 8, "color_threshold": 40}).run(b"image", budget_seconds=0.01)
    assert [r.params["max_colors"] for r in results] == [8]
    assert calls == [8]


def test_invalid_candidate_is_recorded_and_later_candidates_render(colors, monkeypatch):
    def evaluate(self, params, mode):
        if params["max_colors"] == 12:
            raise ValueError("Invalid candidate")
        return scored_by(lambda params: 1.0)(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    failures = []
    results = service(colors, {"max_colors": 8, "color_threshold": 40}).run(
        b"image", on_candidate_error=lambda candidate_id, reason: failures.append((candidate_id, reason)),
    )
    assert [result.candidate_id for result in results] == [1, 3, 4]
    assert failures == [(2, "Invalid candidate")]


def test_unexpected_renderer_failure_remains_fail_stop(colors, monkeypatch):
    def evaluate(self, params, mode):
        if params["max_colors"] == 12:
            raise RuntimeError("Renderer unavailable")
        return scored_by(lambda params: 1.0)(self, params, mode)

    monkeypatch.setattr(Evaluator, "evaluate", evaluate)
    completed = []
    with pytest.raises(RuntimeError, match="Renderer unavailable"):
        service(colors, {"max_colors": 8, "color_threshold": 40}).run(b"image", on_result=completed.append)
    assert [result.candidate_id for result in completed] == [1]


def test_pattern_search_visits_the_coarse_lattice_then_the_best_points_neighbors():
    search = PatternSearch(SearchSpace(
        axes={"a": (1, 2, 3, 4, 5), "b": (10, 20, 30)},
        coarse={"a": (2, 4), "b": (20,)},
    ))
    lattice = [search.next(), search.next()]
    assert lattice == [{"a": 2, "b": 20}, {"a": 4, "b": 20}]
    search.record(lattice[0], 5.0)
    search.record(lattice[1], 1.0)
    neighbors = [search.next() for _ in range(7)]
    # Around a=4, b=20: single-axis steps first, then diagonals.
    assert neighbors == [
        {"a": 5, "b": 20}, {"a": 3, "b": 20}, {"a": 4, "b": 30}, {"a": 4, "b": 10},
        {"a": 5, "b": 30}, {"a": 5, "b": 10}, {"a": 3, "b": 30},
    ]


@pytest.mark.parametrize("mode, name", [
    (mode, name) for mode, recorded in sorted(LANDSCAPES.items()) for name in sorted(recorded["landscapes"])
])
def test_search_finds_the_best_grid_point_on_recorded_landscapes(mode, name):
    recorded = LANDSCAPES[mode]
    space = SEARCH_SPACES[mode]
    assert [(axis, tuple(values)) for axis, values in recorded["axes"].items()] == list(space.axes.items())
    scores = dict(zip(itertools.product(*recorded["axes"].values()), recorded["landscapes"][name]))
    key = lambda params: tuple(params[axis] for axis in space.axes)
    search = PatternSearch(space)
    search.record(recorded["current"], scores[key(recorded["current"])])
    visited = [key(recorded["current"])]
    for _ in range(settings.param_search_trials):
        params = search.next()
        search.record(params, scores[key(params)])
        visited.append(key(params))
    assert len(set(visited)) == len(visited)
    # Recorded scores are rounded to 1e-4; a visible difference is about 1.
    assert min(scores[point] for point in visited) <= min(scores.values()) + 1e-3
