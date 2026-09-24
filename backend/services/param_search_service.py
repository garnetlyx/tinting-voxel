"""Render parameter alternatives with the same pipeline used when applying them."""
import itertools
import logging
import random
import threading
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Callable, Iterator, Optional

import numpy as np
import cv2
from PIL import Image

from core.blend_color import Colors

logger = logging.getLogger(__name__)


@dataclass
class FixedParams:
    layer_count: int
    layer_height: float
    pixel_size: float
    white_backing_layers: int
    backing_mode: str = "white"


@dataclass
class SearchResult:
    candidate_id: int
    is_baseline: bool
    mode: str
    params: dict
    preview_data_url: str


@dataclass
class ParamSearchConfig:
    mode: str
    strategy: str
    n_trials: int
    seed: Optional[int]
    fixed: FixedParams
    colors: Colors
    param_ranges: Optional[dict]
    baseline_params: Optional[dict] = None


class Evaluator:
    def __init__(self, original_image_bytes: bytes, colors: Colors, fixed: FixedParams) -> None:
        self._original_bytes = original_image_bytes
        self._colors = colors
        self._fixed = fixed

    def evaluate(self, params: dict, mode: str) -> SearchResult:
        if mode == "pixel":
            preview_data_url = self._run_pixel(params)
        elif mode == "svg":
            preview_data_url = self._run_svg(params)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        return SearchResult(
            candidate_id=0, is_baseline=False, mode=mode,
            params=dict(params), preview_data_url=preview_data_url,
        )

    def _run_pixel(self, params: dict) -> str:
        from services.image_processor import process_image
        result = process_image(
            image_bytes=self._original_bytes,
            max_colors=int(params.get("max_colors", 10)),
            color_threshold=float(params.get("color_threshold", 50)),
            pixel_size=self._fixed.pixel_size,
            filament_colors=self._colors,
            layer_count=self._fixed.layer_count,
            layer_height=self._fixed.layer_height,
            white_backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
            detail_size=float(params.get("detail_size", 0.42)),
        )
        return result["processedImage"]

    def _run_svg(self, params: dict) -> str:
        from services.image_processor import build_vector_simulated_preview, resample_to_model_grid
        from services.stl_generator import compute_reference_matrices
        from services.vector_processor import VectorProcessorConfig, process_image_vector_with_preview

        img = Image.open(BytesIO(self._original_bytes))
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert("RGB")
        detail_size = float(params.get("detail_size", 0.42))
        img, pixel_size = resample_to_model_grid(img, self._fixed.pixel_size, detail_size)
        config = VectorProcessorConfig(
            epsilon=float(params.get("epsilon", 2.0)),
            min_area=max(1, int(float(params.get("min_area", 4.0)) / (pixel_size * pixel_size))),
            num_colors=int(params.get("num_colors", 8)),
            pixel_size=pixel_size,
            detail_size=detail_size,
        )
        vector_results, quantized = process_image_vector_with_preview(np.array(img), config)
        ref_matrices = compute_reference_matrices(
            self._fixed.layer_count, self._fixed.layer_height, self._colors,
            n_targets=len(vector_results),
            backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
        )
        preview = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            pixel_size=pixel_size,
            detail_size=config.detail_size,
            colors=self._colors,
            layer_count=self._fixed.layer_count,
            layer_height=self._fixed.layer_height,
            white_backing_layers=self._fixed.white_backing_layers,
            backing_mode=self._fixed.backing_mode,
            ref_matrices=ref_matrices,
        )
        return preview["processedImage"]


# Default parameter ranges for grid search
_GRID_DEFAULTS_PIXEL = {
    "max_colors": [6, 8, 10, 12],
    "color_threshold": [20, 40, 60, 80],
    "detail_size": [0.22, 0.42, 0.62],
}

_GRID_DEFAULTS_SVG = {
    "num_colors": [6, 8, 10, 12],
    "epsilon": [1.0, 2.0, 3.0],
    "min_area": [2.0, 4.0, 6.0],
    "detail_size": [0.22, 0.42, 0.62],
}

# Default bounds for random search
_RANDOM_BOUNDS_PIXEL = {
    "max_colors": ("int", 4, 16),
    "color_threshold": ("float", 10, 100),
    "detail_size": ("float", 0.22, 0.82),
}

_RANDOM_BOUNDS_SVG = {
    "num_colors": ("int", 4, 16),
    "epsilon": ("float", 0.5, 5.0),
    "min_area": ("float", 1.0, 10.0),
    "detail_size": ("float", 0.22, 0.82),
}


class GridSearch:
    """Exhaustive Cartesian-product search over discrete parameter ranges."""

    def __init__(self, mode: str, param_ranges: Optional[dict] = None) -> None:
        self._mode = mode
        if param_ranges is not None:
            self._ranges = param_ranges
        elif mode == "svg":
            self._ranges = _GRID_DEFAULTS_SVG
        else:
            self._ranges = _GRID_DEFAULTS_PIXEL

    def generate(self) -> Iterator[dict]:
        """Yield each parameter combination as a dict."""
        keys = list(self._ranges.keys())
        values = [self._ranges[k] for k in keys]
        for combo in itertools.product(*values):
            yield dict(zip(keys, combo))

    def total(self) -> int:
        """Return total number of combinations."""
        result = 1
        for v in self._ranges.values():
            result *= len(v)
        return result


class RandomSearch:
    """Random sampling search over continuous parameter bounds."""

    def __init__(
        self,
        mode: str,
        n_trials: int,
        seed: Optional[int] = None,
        param_bounds: Optional[dict] = None,
    ) -> None:
        self._mode = mode
        self._n_trials = n_trials
        self._seed = seed
        if param_bounds is not None:
            self._bounds = param_bounds
        elif mode == "svg":
            self._bounds = _RANDOM_BOUNDS_SVG
        else:
            self._bounds = _RANDOM_BOUNDS_PIXEL

    def generate(self) -> Iterator[dict]:
        """Yield exactly n_trials parameter combinations."""
        rng = random.Random(self._seed)
        for _ in range(self._n_trials):
            params = {}
            for key, spec in self._bounds.items():
                kind = spec[0]
                if kind == "int":
                    params[key] = rng.randint(int(spec[1]), int(spec[2]))
                elif kind == "float":
                    params[key] = rng.uniform(float(spec[1]), float(spec[2]))
                elif kind == "choice":
                    params[key] = rng.choice(spec[1])
                else:
                    raise ValueError(f"Unknown bound kind: {kind}")
            yield params

    def total(self) -> int:
        return self._n_trials


class ParamSearchService:
    def __init__(self, config: ParamSearchConfig) -> None:
        self._config = config
        self._candidate_cache: Optional[list[tuple[str, dict, bool]]] = None

    def _build_strategy(self, mode: str):
        cfg = self._config
        if cfg.strategy == "random":
            return RandomSearch(mode, cfg.n_trials, cfg.seed, cfg.param_ranges)
        return GridSearch(mode, cfg.param_ranges)

    def _modes(self) -> list[str]:
        return ["pixel", "svg"] if self._config.mode == "both" else [self._config.mode]

    def _candidates(self) -> list[tuple[str, dict, bool]]:
        if self._candidate_cache is not None:
            return self._candidate_cache
        cfg = self._config
        candidates = []
        for mode in self._modes():
            baseline = (cfg.baseline_params or {}).get(mode)
            if baseline is not None:
                candidates.append((mode, dict(baseline), True))
            candidates.extend(
                (mode, params, False)
                for params in self._build_strategy(mode).generate()
                if params != baseline
            )
        self._candidate_cache = candidates
        return candidates

    def total_candidates(self) -> int:
        return len(self._candidates())

    def run(
        self,
        image_bytes: bytes,
        on_result: Optional[Callable[[SearchResult], None]] = None,
        on_candidate_error: Optional[Callable[[int, str], None]] = None,
        cancel: Optional[threading.Event] = None,
        budget_seconds: Optional[float] = None,
    ) -> list[SearchResult]:
        """Render full-resolution alternatives in generation order until stopped.

        Cancellation and the wall budget are checked between candidates, never
        while a candidate is rendering, so an in-flight preview remains exact.
        """
        cfg = self._config
        evaluator = Evaluator(image_bytes, cfg.colors, cfg.fixed)
        candidates = self._candidates()
        results: list[SearchResult] = []
        started = time.monotonic()
        for candidate_id, (mode, params, is_baseline) in enumerate(candidates, start=1):
            if cancel is not None and cancel.is_set():
                break
            if budget_seconds is not None and time.monotonic() - started >= budget_seconds:
                break
            try:
                result = evaluator.evaluate(params, mode)
            except (ValueError, cv2.error) as exc:
                reason = str(exc)
                logger.warning("Param search candidate %d failed: mode=%s params=%s reason=%s", candidate_id, mode, params, reason)
                if on_candidate_error is not None:
                    on_candidate_error(candidate_id, reason)
                continue
            result.candidate_id = candidate_id
            result.is_baseline = is_baseline
            result.params["white_backing_layers"] = cfg.fixed.white_backing_layers
            results.append(result)
            if on_result is not None and (cancel is None or not cancel.is_set()):
                on_result(result)
        return results
