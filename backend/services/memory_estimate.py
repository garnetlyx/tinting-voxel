"""Peak-memory estimates for heavy jobs, and the scale-down suggestions that
bring one back under the budget (settings.heavy_memory_budget_mb).

Sizing rationale (calibrated 2026-10 against the 2026-10-02 OOM crash):

- The real bombs are exact-count quantities: filament-preview materializes
  one dict + JSON text per combination (a 1.95M-combination preview measured
  ~1.3 GB), and a pixel-mode response lists every cell of the model grid.
  Those are computed exactly.
- Stack enumeration (_distinct_reference_colors) keeps one representative per
  distinct 8-bit color. The distinct count is not knowable before blending,
  so it is bounded: opaque sets collapse to the top-layer colors, and
  translucent sets were measured far below 2^20 (5 colors x 10 layers:
  109k distinct of 9.8M codes; 5 x 8: 60k of 390k). The 2^20 bound prices the
  worst plausible case (~0.3 GB) without false-flagging the sets users run.
- Per-unit byte costs below are derived from the array dtypes and Python
  object layouts involved, then rounded up; the calibration script
  (tests/performance/calibrate_memory_estimate.py) re-measures them.
"""
import math
from dataclasses import dataclass, field
from typing import Optional

from config.settings import settings

# One unpaginated filament-preview entry: the {"code","rgb"} dict (with sort
# keys), its string code, rgb list, and its slice of the JSON response text.
PREVIEW_ENTRY_BYTES = 700
# The flat code list built before blending (str + list slot per combination).
PREVIEW_CODE_BYTES = 66

# One enumeration representative: code string, its cells in the padded code
# and rgb DataFrames, plus list/pointer overhead. Per layer: one object cell
# per DataFrame plus one string character.
ENUM_REP_BASE_BYTES = 113
ENUM_REP_PER_LAYER_BYTES = 17
ENUM_DISTINCT_BOUND = 1 << 20
# Chunked blend pipeline (2*threads look-ahead), the 2^24 "seen" bitmap and
# the chunked CIEDE2000 matching pass, as measured.
ENUM_PIPELINE_FIXED_BYTES = 130 * 1024 * 1024

# Model-grid working set per cell in pixel mode: RGB image, int32 labels,
# k-means sample buffers, cleanup copies, two rendered previews, and one
# {'x','y'} dict per cell inside the pydantic response before serialization.
# Calibrated 2026-10: a 2M-cell 5-color x 10-layer job measured 1.56 GB
# (tests/performance/calibrate_memory_estimate.py); 620 B/cell keeps the
# estimate at or above the measured peak.
PIXEL_CELL_BYTES = 620
# Model-grid working set per cell in SVG mode: RGB image, quantized copy,
# region masks and contour arrays (no per-pixel response entries).
SVG_CELL_BYTES = 120
# Rendered preview images: two base64 PNGs bounded by the display edge.
PREVIEW_IMAGE_MAX_BYTES = 2 * 24 * 1024 * 1024

# Merged mesh boxes: capped by settings.stl_max_boxes at run time; each box
# costs its extruded vertices/faces in the generator's float arrays plus the
# serialized STL/3MF bytes.
BOX_BYTES = 220


def _mb(x: float) -> float:
    return x / (1024 * 1024)


def grid_cells(width_px: int, height_px: int, pixel_size: float, detail_size: Optional[float]) -> int:
    """Cells of the model grid an image resamples to (image_processor.model_pitch
    is the single source of the grid policy)."""
    from services.image_processor import model_pitch
    pitch = model_pitch(width_px, height_px, pixel_size, detail_size)
    return (
        max(1, math.floor(width_px * pixel_size / pitch))
        * max(1, math.floor(height_px * pixel_size / pitch))
    )


def enumeration_mb(n_labels: int, layer_count: int) -> float:
    """Representatives + pipeline for one stack search over n_labels^layers codes.

    The distinct-color count is bounded uniformly: measured sets stay far
    below 2^20 whether or not their mean TD reads as opaque (Bambu CMYWK at
    4 layers keeps all 625 codes distinct), so translucency does not change
    the bound.
    """
    codes = n_labels ** layer_count
    distinct = min(codes, ENUM_DISTINCT_BOUND)
    reps = distinct * (ENUM_REP_BASE_BYTES + ENUM_REP_PER_LAYER_BYTES * layer_count)
    return _mb(reps + ENUM_PIPELINE_FIXED_BYTES)


def filament_preview_mb(n_labels: int, layer_count: int, page_size: Optional[int]) -> float:
    """Peak while materializing the preview grid and its JSON response."""
    combos = n_labels ** layer_count
    entries = page_size if page_size else combos
    materialized = entries * PREVIEW_ENTRY_BYTES
    if page_size is None:
        materialized += combos * PREVIEW_CODE_BYTES
    return _mb(materialized + PREVIEW_IMAGE_MAX_BYTES)


def process_image_mb(
    mode: str,
    cells: int,
    n_labels: int,
    layer_count: int,
    n_targets: int,
    translucent: bool,
    backing_layers: int = 3,
) -> float:
    """Peak for one /api/process-image job on a cells-cell model grid."""
    grid = _mb(cells * (PIXEL_CELL_BYTES if mode == "pixel" else SVG_CELL_BYTES))
    enum = enumeration_mb(n_labels, layer_count + backing_layers)
    return grid + enum + _mb(PREVIEW_IMAGE_MAX_BYTES)


def simulate_preview_mb(
    cells: int, n_labels: int, layer_count: int, backing_layers: int = 3,
) -> float:
    """Re-rendering the simulated preview over an existing label map."""
    return (
        _mb(cells * 24 + PREVIEW_IMAGE_MAX_BYTES)
        # A cache miss rebuilds the reference matrix for the current stack.
        + enumeration_mb(n_labels, layer_count + backing_layers)
    )


def download_mb(
    cells: int,
    layer_count: int,
    n_labels: int,
    translucent: bool,
    backing_layers: int = 3,
) -> float:
    """Peak for one STL/3MF export over a cells-cell label map."""
    boxes = min(cells * layer_count, settings.stl_max_boxes)
    return _mb(boxes * BOX_BYTES) + enumeration_mb(n_labels, layer_count + backing_layers)


def batch_mb(images: int, cells_per_image: int) -> float:
    """Batch requests hold every upload's bytes plus run sequentially."""
    return images * (_mb(cells_per_image * PIXEL_CELL_BYTES) + _mb(PREVIEW_IMAGE_MAX_BYTES))


@dataclass
class Reduction:
    """Parameters that bring an estimate under the memory budget."""

    layerCount: Optional[int] = None
    pageSize: Optional[int] = None
    pixelSize: Optional[float] = None

    def as_dict(self) -> dict:
        """JSON-safe body for API responses."""
        out: dict = {}
        if self.layerCount is not None:
            out["layerCount"] = self.layerCount
        if self.pageSize is not None:
            out["pageSize"] = self.pageSize
        if self.pixelSize is not None:
            out["pixelSize"] = round(self.pixelSize, 4)
        return out


@dataclass
class Estimate:
    kind: str
    estimated_mb: float
    budget_mb: float
    within_budget: bool
    suggestion: Optional[Reduction] = None

    def as_dict(self) -> dict:
        out = {
            "kind": self.kind,
            "estimatedMb": round(self.estimated_mb),
            "budgetMb": round(self.budget_mb),
            "withinBudget": self.within_budget,
        }
        if self.suggestion is not None:
            out["suggestion"] = self.suggestion.as_dict()
        return out


def _suggested_preview_page_size() -> int:
    return 10000


# Layer-count suggestions stop here: the UI's layer slider cannot go below
# four, so suggesting fewer would desync the retry from the applied state.
MIN_SUGGESTED_LAYERS = 4


def suggest_filament_preview(
    n_labels: int, layer_count: int, page_size: Optional[int], budget_mb: float
) -> Optional[Reduction]:
    """Paginate first (the grid data is never capped, only its rendering),
    then step the layer count down."""
    if filament_preview_mb(n_labels, layer_count, page_size) <= budget_mb:
        return None
    if page_size is None:
        candidate = Reduction(pageSize=_suggested_preview_page_size())
        if filament_preview_mb(n_labels, layer_count, candidate.pageSize) <= budget_mb:
            return candidate
    for layers in range(layer_count - 1, MIN_SUGGESTED_LAYERS - 1, -1):
        if filament_preview_mb(n_labels, layers, page_size) <= budget_mb:
            return Reduction(layerCount=layers, pageSize=page_size)
    return Reduction(
        layerCount=MIN_SUGGESTED_LAYERS,
        pageSize=page_size if page_size else _suggested_preview_page_size(),
    )


def suggest_process_image(
    mode: str,
    cells: int,
    pixel_size: float,
    n_labels: int,
    layer_count: int,
    n_targets: int,
    translucent: bool,
    budget_mb: float,
) -> Optional[Reduction]:
    """Fewer color layers is the only request-side lever: the model grid
    keeps the upload's own resolution at any pixel size (image_processor.
    model_pitch scales its pitch proportionally), so coarsening pixelSize
    does not reduce cells — it only enlarges the physical output."""
    if process_image_mb(mode, cells, n_labels, layer_count, n_targets, translucent) <= budget_mb:
        return None
    for layers in range(layer_count - 1, MIN_SUGGESTED_LAYERS - 1, -1):
        if process_image_mb(mode, cells, n_labels, layers, n_targets, translucent) <= budget_mb:
            return Reduction(layerCount=layers)
    return None


def suggest_download(
    cells: int,
    n_labels: int,
    layer_count: int,
    translucent: bool,
    budget_mb: float,
) -> Optional[Reduction]:
    """Exports re-use the processed label map, so only layers can come down."""
    if download_mb(cells, layer_count, n_labels, translucent) <= budget_mb:
        return None
    for layers in range(layer_count - 1, MIN_SUGGESTED_LAYERS - 1, -1):
        if download_mb(cells, layers, n_labels, translucent) <= budget_mb:
            return Reduction(layerCount=layers)
    return None
