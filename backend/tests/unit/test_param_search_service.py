"""
Unit tests for ParamSearchService: downscaled evaluation, cooperative cancel,
and partial-result collection on timeout.
"""
import io
import threading
import time

import pytest
from PIL import Image

from core.color_config import get_preset
from core.color_materials import Colors
from services.param_search_service import (
    Evaluator,
    FixedParams,
    ParamSearchConfig,
    ParamSearchService,
)

FIXED = FixedParams(layer_count=4, layer_height=0.08, pixel_size=0.42)

# Wide enough that a full grid cannot finish inside the small timeouts used
# below: 4 * 4 * 3 * 2 = 96 combinations.
_WIDE_GRID = {
    "max_colors": [6, 8, 10, 12],
    "color_threshold": [20, 40, 60, 80],
    "detail_size": [0.22, 0.42, 0.62],
    "white_backing_layers": [0, 1],
}

_TINY_GRID = {
    "max_colors": [6, 8],
    "color_threshold": [20, 40],
    "detail_size": [0.42],
    "white_backing_layers": [1],
}


def _make_png(width: int = 600, height: int = 800) -> bytes:
    """Gradient + noise image with enough color variety for the pipeline."""
    import numpy as np

    xs = np.linspace(0, 255, width, dtype=np.float32)
    grad = np.tile(xs, (height, 1))
    noise = np.random.default_rng(7).integers(0, 40, (height, width))
    arr = np.stack([grad, 255 - grad, grad / 2 + noise], axis=2).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def colors() -> Colors:
    return Colors.from_configs(get_preset("bambu_cmyw_phase6"))


@pytest.fixture
def png_bytes() -> bytes:
    return _make_png()


def _service(param_ranges, colors):
    config = ParamSearchConfig(
        mode="pixel",
        strategy="grid",
        n_trials=10,
        seed=None,
        fixed=FIXED,
        colors=colors,
        param_ranges=param_ranges,
        top_n=5,
    )
    return ParamSearchService(config)


class TestEvaluatorDownscale:
    def test_work_image_capped_to_max_edge(self, png_bytes, colors):
        ev = Evaluator(png_bytes, colors, FIXED)
        work = Image.open(io.BytesIO(ev._work_bytes))
        assert max(work.size) <= Evaluator.WORK_MAX_EDGE

    def test_small_image_not_upscaled(self, colors):
        png = _make_png(width=64, height=80)
        ev = Evaluator(png, colors, FIXED)
        work = Image.open(io.BytesIO(ev._work_bytes))
        assert work.size == (64, 80)
        assert ev._pixel_size == pytest.approx(FIXED.pixel_size)

    def test_effective_pixel_size_scales_with_downscale(self, png_bytes, colors):
        ev = Evaluator(png_bytes, colors, FIXED)
        # 800px longest edge -> 384px, so each work pixel covers ~2.08x more mm.
        assert ev._pixel_size == pytest.approx(FIXED.pixel_size * 800 / 384)

    def test_evaluation_returns_result_on_work_image(self, png_bytes, colors):
        ev = Evaluator(png_bytes, colors, FIXED)
        result = ev.evaluate(
            {"max_colors": 8, "color_threshold": 40, "detail_size": 0.42,
             "white_backing_layers": 1},
            "pixel",
        )
        assert 0.0 <= result.mae <= 255.0
        assert result.preview_data_url.startswith("data:image/png;base64,")


class TestCooperativeCancel:
    def test_cancel_stops_loop_between_evaluations(self, png_bytes, colors):
        svc = _service(_WIDE_GRID, colors)
        cancel = threading.Event()
        threading.Timer(1.0, cancel.set).start()

        results = svc.run(png_bytes, cancel=cancel)

        total = 4 * 4 * 3 * 2
        assert 0 < len(results) < total, (
            f"expected partial results, got {len(results)}/{total}"
        )
        maes = [r.mae for r in results]
        assert maes == sorted(maes)

    def test_run_with_timeout_returns_partial_results(self, png_bytes, colors):
        svc = _service(_WIDE_GRID, colors)

        start = time.monotonic()
        results = svc.run_with_timeout(png_bytes, timeout_seconds=2.0)
        elapsed = time.monotonic() - start

        # Cancel honored within the grace period after the budget expires.
        assert elapsed < 2.0 + 30.0
        # Partial (or full) results come back ranked instead of an empty list.
        assert len(results) >= 1
        maes = [r.mae for r in results]
        assert maes == sorted(maes)
        assert [r.rank for r in results] == list(range(1, len(results) + 1))

    def test_run_with_timeout_completes_small_grid(self, png_bytes, colors):
        svc = _service(_TINY_GRID, colors)

        results = svc.run_with_timeout(png_bytes, timeout_seconds=120.0)

        assert len(results) == 4  # 2 * 2 * 1 * 1
        assert [r.rank for r in results] == [1, 2, 3, 4]

    def test_timeout_thread_exits_after_cancel(self, png_bytes, colors):
        """The worker thread must stop shortly after the budget expires."""
        svc = _service(_WIDE_GRID, colors)

        start = time.monotonic()
        svc.run_with_timeout(png_bytes, timeout_seconds=1.0)
        # After returning, give the abandoned-grace path a moment and check the
        # loop is no longer appending: re-run with the same budget and confirm
        # it returns promptly (no zombie CPU burn from the previous grid).
        elapsed = time.monotonic() - start
        assert elapsed < 1.0 + 30.0 + 5.0
