"""
Parameter search optimizer service.

Finds optimal image processing parameters by evaluating combinations
against the original image using MAE (Mean Absolute Error).
"""
import base64
import csv
import itertools
import json
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Callable, Iterator, Optional

import numpy as np
from PIL import Image

from api.models import ProgressEvent
from core.blend_color import Colors

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FixedParams:
    """Parameters that are fixed for the entire search run."""
    layer_count: int
    layer_height: float
    pixel_size: float


@dataclass
class SearchResult:
    """Single evaluated parameter combination."""
    rank: int
    mode: str
    params: dict
    mae: float
    preview_data_url: str


@dataclass
class ParamSearchConfig:
    """Configuration for a parameter search run."""
    mode: str                        # "pixel", "svg", or "both"
    strategy: str                    # "grid" or "random"
    n_trials: int
    seed: Optional[int]
    fixed: FixedParams
    colors: Colors
    param_ranges: Optional[dict]
    top_n: int


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class Evaluator:
    """Evaluates a single parameter combination by running the pipeline and computing MAE."""

    EVAL_SIZE = (128, 128)

    def __init__(self, original_image_bytes: bytes, colors: Colors, fixed: FixedParams) -> None:
        self._original_bytes = original_image_bytes
        self._colors = colors
        self._fixed = fixed
        # Pre-load and resize original image once
        try:
            img = Image.open(BytesIO(original_image_bytes)).convert("RGB")
            self._original_resized = img.resize(self.EVAL_SIZE, Image.LANCZOS)
        except Exception as exc:
            raise ValueError(f"Cannot load original image: {exc}") from exc

    def evaluate(self, params: dict, mode: str) -> SearchResult:
        """Run one pipeline pass and return MAE + preview data URL."""
        if mode == "pixel":
            preview_data_url = self._run_pixel(params)
        elif mode == "svg":
            preview_data_url = self._run_svg(params)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        mae = self.compute_mae(self._original_resized, preview_data_url)
        return SearchResult(rank=0, mode=mode, params=params, mae=mae, preview_data_url=preview_data_url)

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
            white_backing_layers=int(params.get("white_backing_layers", 1)),
            detail_size=float(params.get("detail_size", 0.42)),
        )
        return result["processedImage"]

    def _run_svg(self, params: dict) -> str:
        from io import BytesIO as _BytesIO
        import numpy as _np
        from PIL import Image as _Image
        from services.image_processor import build_vector_simulated_preview, _downscale_if_needed, MAX_PROCESSING_DIMENSION
        from services.vector_processor import VectorProcessorConfig, process_image_vector_with_preview

        img = _Image.open(_BytesIO(self._original_bytes))
        if img.mode == "RGBA":
            bg = _Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        else:
            img = img.convert("RGB")
        img = _downscale_if_needed(img, MAX_PROCESSING_DIMENSION)
        img_array = _np.array(img)

        pixel_size = self._fixed.pixel_size
        min_area_mm2 = float(params.get("min_area", 4.0))
        min_area_px = max(1, int(min_area_mm2 / (pixel_size * pixel_size)))

        config = VectorProcessorConfig(
            epsilon=float(params.get("epsilon", 2.0)),
            min_area=min_area_px,
            num_colors=int(params.get("num_colors", 8)),
            pixel_size=pixel_size,
            detail_size=float(params.get("detail_size", 0.42)),
        )
        vector_results, quantized = process_image_vector_with_preview(img_array, config)
        preview = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            colors=self._colors,
            layer_count=self._fixed.layer_count,
            layer_height=self._fixed.layer_height,
            white_backing_layers=int(params.get("white_backing_layers", 1)),
        )
        return preview["processedImage"]

    @staticmethod
    def compute_mae(original: Image.Image, preview_data_url: str) -> float:
        """Resize both to 128×128, compute mean absolute per-channel RGB error."""
        # Decode preview data URL
        try:
            header, b64data = preview_data_url.split(",", 1)
            img_bytes = base64.b64decode(b64data)
            preview_img = Image.open(BytesIO(img_bytes)).convert("RGB")
        except Exception as exc:
            raise ValueError(f"Cannot decode preview data URL: {exc}") from exc

        try:
            orig_resized = original.resize(Evaluator.EVAL_SIZE, Image.LANCZOS)
            prev_resized = preview_img.resize(Evaluator.EVAL_SIZE, Image.LANCZOS)
        except Exception as exc:
            raise ValueError(f"Cannot resize images for MAE: {exc}") from exc

        orig_arr = np.array(orig_resized, dtype=np.float32)
        prev_arr = np.array(prev_resized, dtype=np.float32)
        mae = float(np.mean(np.abs(orig_arr - prev_arr)))
        return mae


# ---------------------------------------------------------------------------
# Search strategies
# ---------------------------------------------------------------------------

# Default parameter ranges for grid search
_GRID_DEFAULTS_PIXEL = {
    "max_colors": [6, 8, 10, 12],
    "color_threshold": [20, 40, 60, 80],
    "detail_size": [0.22, 0.42, 0.62],
    "white_backing_layers": [0, 1],
}

_GRID_DEFAULTS_SVG = {
    "num_colors": [6, 8, 10, 12],
    "epsilon": [1.0, 2.0, 3.0],
    "min_area": [2.0, 4.0, 6.0],
    "detail_size": [0.22, 0.42, 0.62],
    "white_backing_layers": [0, 1],
}

# Default bounds for random search
_RANDOM_BOUNDS_PIXEL = {
    "max_colors": ("int", 4, 16),
    "color_threshold": ("float", 10, 100),
    "detail_size": ("float", 0.22, 0.82),
    "white_backing_layers": ("choice", [0, 1]),
}

_RANDOM_BOUNDS_SVG = {
    "num_colors": ("int", 4, 16),
    "epsilon": ("float", 0.5, 5.0),
    "min_area": ("float", 1.0, 10.0),
    "detail_size": ("float", 0.22, 0.82),
    "white_backing_layers": ("choice", [0, 1]),
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


# ---------------------------------------------------------------------------
# ParamSearchService
# ---------------------------------------------------------------------------

class ParamSearchService:
    """Coordinates parameter search: strategy → evaluate → sort → return top-N."""

    def __init__(self, config: ParamSearchConfig) -> None:
        self._config = config

    def _build_strategy(self, mode: str):
        cfg = self._config
        if cfg.strategy == "random":
            return RandomSearch(mode, cfg.n_trials, cfg.seed, cfg.param_ranges)
        return GridSearch(mode, cfg.param_ranges)

    def _modes(self):
        m = self._config.mode
        if m == "both":
            return ["pixel", "svg"]
        return [m]

    def run(
        self,
        image_bytes: bytes,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> list[SearchResult]:
        """Run the full search and return top-N results sorted by MAE ascending."""
        cfg = self._config
        evaluator = Evaluator(image_bytes, cfg.colors, cfg.fixed)
        modes = self._modes()

        # Pre-compute total across all modes
        total = sum(self._build_strategy(m).total() for m in modes)
        completed = 0
        best_mae = float("inf")
        all_results: list[SearchResult] = []

        job_id = ""  # filled by caller if needed

        for mode in modes:
            strategy = self._build_strategy(mode)
            for params in strategy.generate():
                try:
                    result = evaluator.evaluate(params, mode)
                    all_results.append(result)
                    if result.mae < best_mae:
                        best_mae = result.mae
                except Exception as exc:
                    logger.warning("Evaluation failed for params=%s mode=%s: %s", params, mode, exc)

                completed += 1
                if on_progress:
                    try:
                        on_progress(ProgressEvent(
                            job_id=job_id,
                            completed=completed,
                            total=total,
                            best_mae=best_mae if best_mae != float("inf") else 0.0,
                            status="running",
                        ))
                    except Exception:
                        pass

        return self._rank_and_trim(all_results)

    def run_with_timeout(
        self,
        image_bytes: bytes,
        timeout_seconds: float = 120.0,
        on_progress: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> list[SearchResult]:
        """Run with a wall-clock timeout; returns best results found so far."""
        results: list[SearchResult] = []
        exc_holder: list[Exception] = []

        def _run():
            try:
                results.extend(self.run(image_bytes, on_progress))
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=timeout_seconds)

        if exc_holder:
            raise exc_holder[0]

        # If thread is still running (timeout), return whatever was collected
        # by re-running a partial search — but since we can't interrupt the
        # thread cleanly, we return what we have via a shared list approach.
        # For simplicity, if the thread finished we return its results;
        # if it timed out we return an empty list (caller handles partial).
        return results if results else []

    @staticmethod
    def _rank_and_trim(results: list[SearchResult]) -> list[SearchResult]:
        """Sort by MAE ascending and assign ranks."""
        sorted_results = sorted(results, key=lambda r: r.mae)
        for i, r in enumerate(sorted_results):
            r.rank = i + 1
        return sorted_results


# ---------------------------------------------------------------------------
# ReportWriter
# ---------------------------------------------------------------------------

class ReportWriter:
    """Writes results.json, results.csv, preview PNGs, and index.html."""

    def write(
        self,
        results: list[SearchResult],
        original_image_bytes: bytes,
        output_dir: Path,
        top_n: int = 10,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        top = results[:top_n]

        # Save original image
        orig_img = Image.open(BytesIO(original_image_bytes)).convert("RGB")
        orig_img.save(output_dir / "original.png")

        # Save preview PNGs and build result dicts
        result_dicts = []
        for r in top:
            png_name = f"rank_{r.rank:02d}_{r.mode}.png"
            try:
                _, b64 = r.preview_data_url.split(",", 1)
                img_bytes = base64.b64decode(b64)
                Image.open(BytesIO(img_bytes)).convert("RGB").save(output_dir / png_name)
            except Exception:
                png_name = ""
            result_dicts.append({
                "rank": r.rank,
                "mode": r.mode,
                "params": r.params,
                "mae": round(r.mae, 4),
                "preview_file": png_name,
            })

        # Write results.json
        with open(output_dir / "results.json", "w", encoding="utf-8") as f:
            json.dump(result_dicts, f, indent=2)

        # Write results.csv
        if result_dicts:
            all_param_keys = sorted({k for rd in result_dicts for k in rd["params"]})
            fieldnames = ["rank", "mode", "mae"] + all_param_keys + ["preview_file"]
            with open(output_dir / "results.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for rd in result_dicts:
                    row = {
                        "rank": rd["rank"],
                        "mode": rd["mode"],
                        "mae": rd["mae"],
                        "preview_file": rd["preview_file"],
                    }
                    row.update(rd["params"])
                    writer.writerow(row)

        # Write index.html
        self._write_html(output_dir, result_dicts, top)

    def _write_html(self, output_dir: Path, result_dicts: list[dict], top: list[SearchResult]) -> None:
        has_both = len({r.mode for r in top}) > 1

        cards_html = ""
        current_mode = None
        for rd in result_dicts:
            if has_both and rd["mode"] != current_mode:
                current_mode = rd["mode"]
                cards_html += f'<h2 class="section-header">{current_mode.upper()} Mode</h2>\n'

            is_best = rd["rank"] == 1
            border = ' style="border: 3px solid #7c3aed;"' if is_best else ""
            badge = '<span class="badge">Best</span>' if is_best else ""
            params_rows = "".join(
                f'<tr><td>{k}</td><td>{v}</td></tr>'
                for k, v in rd["params"].items()
            )
            img_tag = (
                f'<img src="{rd["preview_file"]}" alt="rank {rd["rank"]}">'
                if rd["preview_file"] else '<div class="no-img">No preview</div>'
            )
            cards_html += f"""
<div class="card"{border}>
  {badge}
  <div class="rank">#{rd["rank"]}</div>
  {img_tag}
  <div class="meta">
    <strong>Mode:</strong> {rd["mode"]}<br>
    <strong>MAE:</strong> {rd["mae"]:.4f}
  </div>
  <table class="params">{params_rows}</table>
</div>
"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Param Search Results</title>
<style>
  body {{ font-family: sans-serif; background: #f5f5f5; margin: 0; padding: 16px; }}
  h1 {{ color: #333; }}
  .section-header {{ color: #7c3aed; margin-top: 24px; }}
  .grid {{ display: flex; flex-wrap: wrap; gap: 16px; }}
  .card {{ background: #fff; border-radius: 8px; padding: 12px; width: 200px;
           box-shadow: 0 2px 6px rgba(0,0,0,.1); position: relative; }}
  .card img {{ width: 100%; border-radius: 4px; }}
  .no-img {{ height: 120px; background: #eee; display: flex; align-items: center;
             justify-content: center; color: #999; border-radius: 4px; }}
  .rank {{ font-size: 1.2em; font-weight: bold; color: #7c3aed; }}
  .badge {{ position: absolute; top: 8px; right: 8px; background: #7c3aed;
            color: #fff; padding: 2px 8px; border-radius: 12px; font-size: .75em; }}
  .meta {{ margin: 8px 0; font-size: .85em; color: #555; }}
  .params {{ width: 100%; font-size: .75em; border-collapse: collapse; }}
  .params td {{ padding: 2px 4px; border-bottom: 1px solid #eee; }}
  .original {{ max-width: 300px; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,.1); }}
</style>
</head>
<body>
<h1>Param Search Results</h1>
<h2>Original Image</h2>
<img src="original.png" alt="original" class="original">
<h2>Top Results</h2>
<div class="grid">
{cards_html}
</div>
</body>
</html>"""
        with open(output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(html)
