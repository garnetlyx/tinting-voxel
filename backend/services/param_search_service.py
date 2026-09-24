"""Search for the settings whose simulated print best matches the image.

Each candidate is rendered by the pipeline used when its settings are applied
and scored by the mean CIEDE2000 between the image on the model grid and the
candidate's simulated print (lower is closer). Candidates come from a pattern
search on a fixed grid per mode: a coarse lattice first, then the unvisited
neighbors of the best-scoring point not yet expanded, until the trial budget
is spent. The model size, detail size and print stack stay at the user's
values, so every candidate prints on the same model grid.
"""
import base64
import itertools
import logging
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Iterator, Optional

import cv2
import numpy as np
from PIL import Image

from config.settings import settings
from core.blend_color import Colors
from core.color_materials import mean_ciede2000

logger = logging.getLogger(__name__)


@dataclass
class FixedParams:
    layer_count: int
    layer_height: float
    pixel_size: float
    white_backing_layers: int
    detail_size: float
    backing_mode: str = "white"


@dataclass
class SearchResult:
    candidate_id: int
    is_baseline: bool
    mode: str
    params: dict
    preview_data_url: str
    score: float  # mean CIEDE2000 from the image, lower is closer


@dataclass(frozen=True)
class SearchSpace:
    """Ascending grid values per parameter, and the coarse lattice visited first.

    A point's neighbors are one grid step away along one axis, and along any
    combination of axes when diagonal.
    """
    axes: dict[str, tuple]
    coarse: dict[str, tuple]
    diagonal: bool = True


def _color_counts(values: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(value for value in values if value <= settings.max_target_colors)


# Chosen on exhaustive score landscapes (tests/fixtures/search_landscapes.json):
# from the app defaults, 20 trials reach the best grid point, to within 0.01,
# on every recorded image and filament set. In SVG mode the color count
# dominates and epsilon and minimum area change the score smoothly, so
# single-axis steps suffice.
SEARCH_SPACES = {
    "pixel": SearchSpace(
        axes={
            "max_colors": _color_counts((2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 48, 64, 100)),
            "color_threshold": (10, 15, 20, 30, 40, 50, 60, 70, 80, 90, 100),
        },
        coarse={"max_colors": _color_counts((6, 20, 64)), "color_threshold": (10, 15, 40)},
    ),
    "svg": SearchSpace(
        axes={
            "num_colors": (2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32),
            "epsilon": (0.5, 1.0, 2.0, 3.0, 5.0),
            "min_area": (0.1, 0.5, 1.0, 2.0, 4.0, 8.0),
        },
        coarse={"num_colors": (5, 10, 20, 32), "epsilon": (1.0,), "min_area": (1.0,)},
        diagonal=False,
    ),
}


@dataclass
class ParamSearchConfig:
    mode: str
    n_trials: int
    fixed: FixedParams
    colors: Colors
    baseline_params: dict  # the user's current values of the mode's parameters
    space: Optional[SearchSpace] = None  # defaults to SEARCH_SPACES[mode]


class PatternSearch:
    """Grid points in the order a pattern search visits them.

    Every reported point counts as visited; a failed point ranks last, so the
    grid stays connected and every point is reached eventually.
    """

    def __init__(self, space: SearchSpace) -> None:
        self._names = list(space.axes)
        self._axes = [space.axes[name] for name in self._names]
        self._queue = deque(itertools.product(*(
            [values.index(value) for value in space.coarse[name]]
            for name, values in zip(self._names, self._axes)
        )))
        # One grid step along one axis first, then along combinations of axes.
        self._steps = sorted(
            (step for step in itertools.product((1, -1, 0), repeat=len(self._axes))
             if any(step) and (space.diagonal or sum(map(bool, step)) == 1)),
            key=lambda step: sum(map(bool, step)),
        )
        self._visited: set[tuple[int, ...]] = set()
        self._scores: dict[tuple[int, ...], float] = {}
        self._expanded: set[tuple[int, ...]] = set()

    @property
    def size(self) -> int:
        return math.prod(len(values) for values in self._axes)

    def point(self, params: dict) -> Optional[tuple[int, ...]]:
        """Grid indices of params, or None when any value is off the grid."""
        try:
            return tuple(values.index(params[name]) for name, values in zip(self._names, self._axes))
        except (KeyError, ValueError):
            return None

    def next(self) -> Optional[dict]:
        """The next unvisited point's parameters, or None once all are visited."""
        while True:
            while self._queue:
                point = self._queue.popleft()
                if point not in self._visited:
                    self._visited.add(point)
                    return {name: values[i] for name, values, i in zip(self._names, self._axes, point)}
            unexpanded = [point for point in self._scores if point not in self._expanded]
            if not unexpanded:
                return None
            center = min(unexpanded, key=self._scores.__getitem__)
            self._expanded.add(center)
            self._queue.extend(self._neighbors(center))

    def record(self, params: dict, score: Optional[float]) -> None:
        """Report a score; None marks a point that failed to render."""
        point = self.point(params)
        if point is not None:
            self._visited.add(point)
            self._scores[point] = math.inf if score is None else score

    def _neighbors(self, center: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        for step in self._steps:
            point = tuple(index + delta for index, delta in zip(center, step))
            if all(0 <= index < len(values) for index, values in zip(point, self._axes)):
                yield point


def _decode_preview(data_url: str) -> np.ndarray:
    encoded = data_url.split(",", 1)[1]
    return np.asarray(Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB"))


class Evaluator:
    """Renders settings as applying them would, and scores the simulated print."""

    def __init__(self, original_image_bytes: bytes, colors: Colors, fixed: FixedParams) -> None:
        self._original_bytes = original_image_bytes
        self._colors = colors
        self._fixed = fixed
        self._grid: Optional[tuple[np.ndarray, float]] = None

    def model_grid(self) -> tuple[np.ndarray, float]:
        """The image on its model grid (read-only RGB) and the grid pitch in mm."""
        if self._grid is None:
            from services.image_processor import load_model_grid
            image, pitch = load_model_grid(self._original_bytes, self._fixed.pixel_size, self._fixed.detail_size)
            pixels = np.array(image)
            pixels.setflags(write=False)
            self._grid = pixels, pitch
        return self._grid

    def evaluate(self, params: dict, mode: str) -> SearchResult:
        if mode == "pixel":
            preview_data_url = self._run_pixel(params)
        elif mode == "svg":
            preview_data_url = self._run_svg(params)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        score = mean_ciede2000(self.model_grid()[0], _decode_preview(preview_data_url))
        return SearchResult(
            candidate_id=0, is_baseline=False, mode=mode,
            params=dict(params), preview_data_url=preview_data_url, score=score,
        )

    def _run_pixel(self, params: dict) -> str:
        from services.image_processor import process_image
        result = process_image(
            image_bytes=self._original_bytes,
            max_colors=int(params["max_colors"]),
            color_threshold=float(params["color_threshold"]),
            pixel_size=self._fixed.pixel_size,
            filament_colors=self._colors,
            layer_count=self._fixed.layer_count,
            layer_height=self._fixed.layer_height,
            white_backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
            detail_size=self._fixed.detail_size,
        )
        return result["processedImage"]

    def _run_svg(self, params: dict) -> str:
        from services.image_processor import build_vector_simulated_preview
        from services.stl_generator import compute_reference_matrices
        from services.vector_processor import VectorProcessorConfig, process_image_vector_with_preview

        pixels, pitch = self.model_grid()
        config = VectorProcessorConfig(
            epsilon=float(params["epsilon"]),
            min_area=max(1, int(float(params["min_area"]) / (pitch * pitch))),
            num_colors=int(params["num_colors"]),
            pixel_size=pitch,
            detail_size=self._fixed.detail_size,
        )
        vector_results, quantized = process_image_vector_with_preview(pixels, config)
        ref_matrices = compute_reference_matrices(
            self._fixed.layer_count, self._fixed.layer_height, self._colors,
            n_targets=len(vector_results),
            backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
        )
        preview = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            pixel_size=pitch,
            detail_size=config.detail_size,
            colors=self._colors,
            layer_count=self._fixed.layer_count,
            layer_height=self._fixed.layer_height,
            white_backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
            ref_matrices=ref_matrices,
        )
        return preview["processedImage"]


class ParamSearchService:
    def __init__(self, config: ParamSearchConfig) -> None:
        self._config = config
        self._space = config.space or SEARCH_SPACES[config.mode]

    def total_candidates(self) -> int:
        """The current settings plus up to n_trials other grid points."""
        search = PatternSearch(self._space)
        other_points = search.size - (search.point(self._config.baseline_params) is not None)
        return 1 + min(self._config.n_trials, other_points)

    def run(
        self,
        image_bytes: bytes,
        on_result: Optional[Callable[[SearchResult], None]] = None,
        on_candidate_error: Optional[Callable[[int, str], None]] = None,
        cancel: Optional[threading.Event] = None,
        budget_seconds: Optional[float] = None,
    ) -> list[SearchResult]:
        """Render and score the current settings, then search, until done or stopped.

        Cancellation and the wall budget are checked between candidates, never
        while a candidate is rendering, so an in-flight preview remains exact.
        """
        cfg = self._config
        evaluator = Evaluator(image_bytes, cfg.colors, cfg.fixed)
        search = PatternSearch(self._space)
        results: list[SearchResult] = []
        started = time.monotonic()
        for candidate_id in range(1, self.total_candidates() + 1):
            if cancel is not None and cancel.is_set():
                break
            if budget_seconds is not None and time.monotonic() - started >= budget_seconds:
                break
            if candidate_id == 1:
                params = dict(cfg.baseline_params)
            else:
                point = search.next()
                if point is None:
                    break
                # Parameters the space does not search keep the user's values.
                params = {**cfg.baseline_params, **point}
            try:
                result = evaluator.evaluate(params, cfg.mode)
            except (ValueError, cv2.error) as exc:
                reason = str(exc)
                logger.warning("Param search candidate %d failed: mode=%s params=%s reason=%s", candidate_id, cfg.mode, params, reason)
                search.record(params, None)
                if on_candidate_error is not None:
                    on_candidate_error(candidate_id, reason)
                continue
            search.record(params, result.score)
            result.candidate_id = candidate_id
            result.is_baseline = candidate_id == 1
            result.params.update(
                detail_size=cfg.fixed.detail_size,
                white_backing_layers=cfg.fixed.white_backing_layers,
            )
            results.append(result)
            if on_result is not None and (cancel is None or not cancel.is_set()):
                on_result(result)
        return results
