"""
STL generation service with color mapping and mesh merging

Includes optimization via greedy meshing to reduce file sizes.
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import itertools
import logging
import threading
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import settings
from core.blend_color import BlendTestGenerator, Color, Colors, colors_key
from core.blend_models import blend_tables, rgb_from_indices
from core.parallel import available_cpus, set_worker_threads, worker_threads
from services.mesh_optimizer import boxes_from_rectangles, greedy_mesh_2d, pixels_to_grid
from services.print_stack import (
    backing_suffix,
    build_print_stack,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)

logger = logging.getLogger(__name__)

# Probe-calibrated throughput for the enumeration cost model (self-adjusting
# to the host CPU; measured once, cached). See _probe_throughput.
_probe_state: dict = {}

# Codes blended per enumeration work item; bounds per-thread temporaries.
_ENUMERATION_CHUNK_CODES = 1 << 14

# Global reference-matrix state (module-level cache for the legacy
# initialize_color_mapping path used by tests and warmup).
_reference_code_matrix = None
_reference_rgb_matrix = None
_blend_generator = None
_current_colors = None
_global_state_lock = threading.Lock()


def _distinct_reference_colors(
    colors: Colors,
    layer_count: int,
    layer_height: float,
    suffix: str = '',
    boundary: Optional[tuple] = None,
    code_list: Optional[list[str]] = None,
) -> tuple[list[str], list[tuple[int, int, int]]]:
    """One (code, 8-bit color) per distinct reference color.

    Codes are visited in enumeration order: the ordered product of the
    labels (first layer most significant), or ``code_list``. Each color keeps
    the first code that renders it, so nearest-color matching over these
    representatives returns what matching over every code returns: equal
    colors have equal distances, and argmin keeps the earliest candidate.
    Blending runs on index arrays in parallel chunks; only representatives
    become strings.
    """
    labels, t_table, absorb_table = blend_tables(layer_height, colors_key(colors))
    n_labels = len(labels)
    label_idx = {label: i for i, label in enumerate(labels)}
    suffix_idx = np.array([label_idx[c] for c in suffix], dtype=np.int64)
    if code_list is None:
        total = n_labels ** layer_count
    else:
        lookup = np.zeros(128, dtype=np.int64)
        for label, i in label_idx.items():
            lookup[ord(label)] = i
        encoded = np.frombuffer(''.join(code_list).encode('ascii'), dtype=np.uint8)
        encoded = encoded.reshape(len(code_list), layer_count)
        total = len(code_list)

    def chunk_keys(start: int) -> np.ndarray:
        stop = min(start + _ENUMERATION_CHUNK_CODES, total)
        if code_list is None:
            flat = np.arange(start, stop, dtype=np.int64)
            digits = np.empty((stop - start, layer_count), dtype=np.int64)
            for position in range(layer_count - 1, -1, -1):
                digits[:, position] = flat % n_labels
                flat //= n_labels
        else:
            digits = lookup[encoded[start:stop]]
        if len(suffix_idx):
            digits = np.concatenate(
                [digits, np.broadcast_to(suffix_idx, (len(digits), len(suffix_idx)))], axis=1,
            )
        rgb = np.round(rgb_from_indices(digits, t_table, absorb_table, boundary)).astype(np.uint32)
        return (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]

    seen = np.zeros(1 << 24, dtype=bool)
    rep_index: list[np.ndarray] = []
    rep_key: list[np.ndarray] = []

    def keep_first_occurrences(start: int, keys: np.ndarray) -> None:
        unique, first = np.unique(keys, return_index=True)
        fresh = ~seen[unique]
        unique, first = unique[fresh], first[fresh]
        order = np.argsort(first, kind='stable')
        seen[unique] = True
        rep_index.append(start + first[order])
        rep_key.append(unique[order])

    starts = range(0, total, _ENUMERATION_CHUNK_CODES)
    threads = worker_threads()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        # Bounded look-ahead keeps finished chunks from piling up in memory;
        # chunks are consumed in order so first occurrences stay first.
        pending: deque = deque()
        for start in starts:
            pending.append((start, pool.submit(chunk_keys, start)))
            if len(pending) >= 2 * threads:
                done_start, future = pending.popleft()
                keep_first_occurrences(done_start, future.result())
        while pending:
            done_start, future = pending.popleft()
            keep_first_occurrences(done_start, future.result())

    index = np.concatenate(rep_index)
    keys = np.concatenate(rep_key)
    if code_list is None:
        digits = np.empty((len(index), layer_count), dtype=np.int64)
        flat = index.copy()
        for position in range(layer_count - 1, -1, -1):
            digits[:, position] = flat % n_labels
            flat //= n_labels
        label_array = np.array(labels)
        codes = [''.join(row) for row in label_array[digits].tolist()]
    else:
        codes = [code_list[i] for i in index.tolist()]
    rgb = np.stack([(keys >> 16) & 255, (keys >> 8) & 255, keys & 255], axis=1)
    return codes, [tuple(row) for row in rgb.tolist()]


def _probe_throughput() -> tuple[float, float]:
    """Measure the enumeration and matching rates on this host.

    Times the enumeration on one thread and on every usable CPU (capped by
    settings.compute_threads) and keeps the faster for all vectorized work.
    Returns seconds per enumerated code (blend, dedup and representative
    decoding) and seconds per (reference color x target) match under the
    production metric. Both stages are linear in their counts.
    """
    if _probe_state:
        return _probe_state["build_s_per_code"], _probe_state["match_s_per_ref_target"]
    import time as _time
    from core.color_materials import Color as _C
    probe_colors = Colors(colors={
        l: _C(l, td, h) for l, h, td in zip(
            "ABCD",
            ["#3D79C6", "#B3356E", "#FFE665", "#FFFFFF"],
            [0.5, 0.5, 0.6, 0.6],
        )
    })
    layers = 9  # 262,144 codes: a real full enumeration
    _distinct_reference_colors(probe_colors, 4, 0.08)  # warm up numpy
    cpus = available_cpus()
    rates: dict[int, float] = {}
    for threads in sorted({1, min(settings.compute_threads, cpus)}):
        set_worker_threads(threads)
        t0 = _time.perf_counter()
        codes, rgbs = _distinct_reference_colors(probe_colors, layers, 0.08)
        rates[threads] = (_time.perf_counter() - t0) / (4 ** layers)
    threads = min(rates, key=rates.get)
    set_worker_threads(threads)
    build = rates[threads]

    targets = [(120 + i, 130 + i % 7, 140) for i in range(64)]
    code_df, rgb_df = _as_matrices(codes, rgbs)
    t0 = _time.perf_counter()
    _C.map_to_nearest_color(targets, code_df, rgb_df)
    match = (_time.perf_counter() - t0) / (len(codes) * len(targets))
    _probe_state.update(build_s_per_code=build, match_s_per_ref_target=match)
    logger.info(
        "Enumeration cost probe: %d usable CPUs, build s/code by threads %s -> %d threads; "
        "match %.2e s/(color x target)",
        cpus, {t: f"{r:.2e}" for t, r in rates.items()}, threads, match,
    )
    return build, match


def _estimate_build_seconds(n_codes: int) -> float:
    """Wall time to enumerate n_codes and keep their distinct colors."""
    return n_codes * _probe_throughput()[0]


def _estimate_match_seconds(n_references: int, n_targets: int) -> float:
    """Wall time to match n_targets against n_references distinct colors."""
    return n_references * n_targets * _probe_throughput()[1]


def _as_matrices(codes: list[str], rgbs: list[tuple]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lay codes and colors out as padded rectangular DataFrames.

    Padding repeats the last entry, which matching never prefers (argmin keeps
    the first of equal distances).
    """
    n = len(codes)
    rows = int(np.sqrt(n))
    cols = (n + rows - 1) // rows
    pad_count = rows * cols - n
    codes_padded = codes + [codes[-1]] * pad_count
    rgbs_padded = rgbs + [rgbs[-1]] * pad_count
    code_df = pd.DataFrame([codes_padded[i * cols:(i + 1) * cols] for i in range(rows)])
    rgb_df = pd.DataFrame([rgbs_padded[i * cols:(i + 1) * cols] for i in range(rows)])
    return code_df, rgb_df


from core.blend_models import codes_to_rgb_batch


def _build_codes_to_rgb(colors: Colors, layer_count: int, layer_height: float,
                        backing_suffix: str = '', background_rgb: Optional[tuple] = None):
    """Batch blend callable consistent with compute_reference_matrices."""
    if backing_suffix or background_rgb is not None:
        def _codes_to_rgb_backing(codes):
            return codes_to_rgb_batch(
                [c + backing_suffix for c in codes],
                layer_height,
                colors_key(colors),
                background_rgb=background_rgb,
            )
        return _codes_to_rgb_backing
    generator = BlendTestGenerator(
        colors=colors,
        layer_height=layer_height,
        layer_count_max=layer_count,
    )
    return generator.codes_to_rgb


def compute_reference_matrices(
    layer_count: int,
    layer_height: float,
    colors: Colors,
    prune: Optional[bool] = None,
    n_targets: Optional[int] = None,
    backing_layers: Optional[int] = None,
    backing_mode: str = 'white',
) -> tuple:
    """
    Compute color reference matrices for Beer-Lambert mapping.

    The matrices hold one representative code per distinct 8-bit reference
    color (see _distinct_reference_colors), so matching them is equivalent
    to matching every candidate code. Thread-safe: returns cached or new
    matrices without modifying global state.

    Args:
        layer_count: Number of layers for color blending
        layer_height: Height of each layer in mm
        colors: Colors instance defining the filament configuration
        n_targets: Number of input colors that will be matched against the
            matrix; the matching pass is part of the wall-time decision

    Returns:
        Tuple of (code_matrix, rgb_matrix) as DataFrames

    prune:
        None (default) enumerates every ordered code whenever the estimated
        enumeration plus matching time fits settings.full_enumeration_budget_seconds,
        and otherwise uses one representative per composition for translucent
        sets; False forces full enumeration (the oracle for the pruned path).
        Pruning is never applied outside the translucent regime.

    Raises:
        ValueError: If the estimate exceeds the budget for a set that cannot
            be pruned (opaque/mixed)
    """
    if layer_count <= 0:
        raise ValueError(f"layer_count must be positive, got {layer_count}")

    # Printed backing block: real trailing layers over the mode boundary —
    # the simulation runs BEFORE mapping, so the backing thickness shifts
    # every candidate color (paper setup, adapted: finite printed backing
    # instead of an infinite external one).
    from services.print_stack import (
        PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label,
    )
    b_label = resolve_backing_label(colors, backing_layers, backing_mode)
    b_suffix = backing_suffix(b_label, backing_layers)
    b_boundary = PRINT_BACKGROUND_RGB if b_suffix else None

    items = colors.get_labels()
    if not items:
        raise ValueError("Colors instance has no colors defined")
    permutation_count = len(items) ** layer_count

    if prune is True:
        raise ValueError(
            "prune=True is not supported: pruning applies automatically and "
            "only to translucent sets. Use prune=None (automatic) or "
            "prune=False (full-enumeration oracle)."
        )

    from core.stack_prune import composition_codes, is_translucent_set
    from services.matrix_cache import get_cached_matrices, set_cached_matrices

    budget = settings.full_enumeration_budget_seconds
    targets = n_targets or 10
    cache_args = dict(backing_suffix=b_suffix, background_rgb=b_boundary)

    # Full enumeration: every ordered code, reduced to its distinct colors.
    # The matrix cache serves every caller (process, downloads, batch,
    # search); the target count only decides whether to use it.
    full = get_cached_matrices(colors, layer_count, layer_height, pruned=False, **cache_args)
    estimated = 0.0 if full is not None else _estimate_build_seconds(permutation_count)
    if full is None and (estimated <= budget or prune is False):
        codes, rgbs = _distinct_reference_colors(colors, layer_count, layer_height, b_suffix, b_boundary)
        full = _as_matrices(codes, rgbs)
        set_cached_matrices(colors, layer_count, layer_height, *full, pruned=False, **cache_args)
        logger.info(
            "Enumerated %d codes (%d colors x %d layers): %d distinct colors",
            permutation_count, len(items), layer_count, len(codes),
        )
    if full is not None:
        estimated += _estimate_match_seconds(full[0].size, targets)
        if prune is False or estimated <= budget:
            return full

    if not is_translucent_set(colors):
        # Composition pruning is validated only for translucent sets.
        raise ValueError(
            f"Stack search for {len(items)} colors x {layer_count} layers "
            f"({permutation_count:,} codes) is estimated at {estimated:.0f}s, over the "
            f"{budget:.0f}s budget, and composition pruning is not validated for a "
            f"non-transparent set. Reduce the number of colors or layers."
        )

    # Translucent regime over budget: one canonical representative per
    # composition (C(N+L-1, L) candidates; see core/stack_prune.py); order is
    # recovered per match by refine_matches().
    pruned = get_cached_matrices(colors, layer_count, layer_height, pruned=True, **cache_args)
    if pruned is None:
        compositions = composition_codes(items, layer_count)
        codes, rgbs = _distinct_reference_colors(
            colors, layer_count, layer_height, b_suffix, b_boundary, code_list=compositions,
        )
        pruned = _as_matrices(codes, rgbs)
        set_cached_matrices(colors, layer_count, layer_height, *pruned, pruned=True, **cache_args)
        logger.info(
            "Pruned stack candidates: %d compositions of %d colors x %d layers, "
            "%d distinct colors (full estimate %.0fs over %.0fs budget)",
            len(compositions), len(items), layer_count, len(codes), estimated, budget,
        )
    return pruned


def map_color_blocks_to_blend_results(
    color_blocks: list[dict],
    layer_height: float,
    layer_count: int,
    colors: Colors,
    backing_layers: Optional[int] = None,
    backing_mode: str = 'white',
) -> tuple[list[str], list[tuple[int, int, int]]]:
    """
    Map source RGB blocks to nearest printable blend codes and RGBs.

    Uses the same reference matrices and LAB nearest-neighbor matching as STL export.
    The printed backing block participates in the simulation (backing-aware
    matrices); returned codes carry the backing as a trailing suffix.
    """
    from services.print_stack import (
        PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label,
    )
    b_label = resolve_backing_label(colors, backing_layers, backing_mode)
    b_suffix = backing_suffix(b_label, backing_layers)
    b_boundary = PRINT_BACKGROUND_RGB if b_suffix else None
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count,
        layer_height,
        colors,
        n_targets=len(input_colors),
        backing_layers=backing_layers,
        backing_mode=backing_mode,
    )
    result_codes, result_rgbs = Color.map_to_nearest_color(
        input_colors,
        ref_code_matrix,
        ref_rgb_matrix,
    )
    # Translucent sets match against composition representatives; recover the
    # best ordering across the top compositions (no-op for opaque sets).
    from core.stack_prune import refine_matches
    result_codes, result_rgbs = refine_matches(
        input_colors,
        result_codes,
        result_rgbs,
        ref_code_matrix,
        ref_rgb_matrix,
        colors,
        layer_height,
        codes_to_rgb=_build_codes_to_rgb(
            colors, layer_count, layer_height,
            backing_suffix=b_suffix, background_rgb=b_boundary,
        ),
    )
    normalized_rgbs = [
        tuple(int(channel) for channel in np.asarray(rgb).tolist())
        for rgb in result_rgbs
    ]
    return [code + b_suffix for code in result_codes], normalized_rgbs


def _log_blend_code_distribution(
    result_codes: list[str],
    labels: list[str],
    generator_name: str = "STL"
) -> dict[str, int]:
    """
    Log blend code distribution to help diagnose missing filament colors.

    Args:
        result_codes: List of blend code strings (e.g., ["CCMY", "CCCC", ...])
        labels: All available filament labels (e.g., ["C", "M", "Y", "W"])
        generator_name: Name for log messages

    Returns:
        Dict mapping each label to its total layer count
    """
    from collections import Counter

    char_counts: Counter = Counter()
    code_counts: Counter = Counter()
    for code in result_codes:
        code_counts[code] += 1
        for ch in code:
            char_counts[ch] += 1

    total_layers = sum(char_counts.values())

    label_stats = []
    absent_labels = []
    for label in labels:
        count = char_counts.get(label, 0)
        pct = (count / total_layers * 100) if total_layers > 0 else 0
        label_stats.append(f"{label}={count} ({pct:.1f}%)")
        if count == 0:
            absent_labels.append(label)

    logger.info(
        "%s blend codes (%d blocks, %d layers): %s",
        generator_name, len(result_codes), total_layers,
        ", ".join(label_stats)
    )

    top_codes = code_counts.most_common(5)
    logger.info(
        "%s top codes: %s",
        generator_name,
        ", ".join(f"{code}={count}" for code, count in top_codes)
    )

    if absent_labels:
        logger.warning(
            "%s: filament(s) %s not used in any blend code",
            generator_name, ", ".join(absent_labels)
        )

    return dict(char_counts)


def _log_input_color_brightness(
    input_colors: list[tuple[int, int, int]],
    generator_name: str = "STL"
) -> None:
    """
    Log brightness statistics for input colors.

    Helps diagnose why White filament may not appear — if no input colors
    are near-white, the mapping will never select W layers.
    """
    if not input_colors:
        return

    brightnesses = [
        (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
        for r, g, b in input_colors
    ]
    avg_brightness = sum(brightnesses) / len(brightnesses)
    max_brightness = max(brightnesses)
    near_white = sum(1 for b in brightnesses if b > 0.85)

    logger.info(
        "%s input brightness: avg=%.2f, max=%.2f, near-white (>85%%): %d/%d",
        generator_name, avg_brightness, max_brightness,
        near_white, len(input_colors)
    )


def initialize_color_mapping(
    layer_count: int = 4,
    layer_height: float = 0.08,
    colors: Optional[Colors] = None
):
    """
    Initialize global color mapping reference matrices.

    Thread-safe: Uses lock to protect global state during initialization.

    Used for app startup caching. For request-scoped operations,
    prefer passing colors directly to generate_stl_zip() which
    computes matrices locally (thread-safe).

    Args:
        layer_count: Number of layers for color blending
        layer_height: Height of each layer in mm
        colors: Optional Colors instance. If None, uses the default Bambu CMYWK.
    """
    global _reference_code_matrix, _reference_rgb_matrix, _blend_generator, _current_colors

    if colors is None:
        colors = Colors()

    with _global_state_lock:
        _current_colors = colors
        _blend_generator = BlendTestGenerator(
            colors=colors,
            layer_height=layer_height,
            layer_count_max=layer_count,
        )

        _reference_code_matrix, _reference_rgb_matrix = compute_reference_matrices(
            layer_count, layer_height, colors
        )


def generate_box(
    xrange: tuple[float, float],
    yrange: tuple[float, float],
    zrange: tuple[float, float]
) -> np.ndarray:
    """
    Generate a 3D box mesh for a single pixel

    Args:
        xrange: (x_min, x_max) in mm
        yrange: (y_min, y_max) in mm
        zrange: (z_min, z_max) in mm

    Returns:
        Numpy array of mesh vertices (12 triangles x 3 vertices x 3 coords)
    """
    x1, x2 = xrange
    y1, y2 = yrange
    z1, z2 = zrange

    # Validate non-negative coordinates (QA-167)
    if x1 < 0 or x2 < 0 or y1 < 0 or y2 < 0 or z1 < 0 or z2 < 0:
        raise ValueError(f"All coordinates must be non-negative, got xrange={xrange}, yrange={yrange}, zrange={zrange}")

    # Validate non-inverted ranges (QA-168)
    if x1 >= x2 or y1 >= y2 or z1 >= z2:
        raise ValueError(f"Range start must be less than end, got xrange={xrange}, yrange={yrange}, zrange={zrange}")

    # 8 vertices of the box
    vertices = np.array([
        [x1, y1, z1],
        [x2, y1, z1],
        [x2, y2, z1],
        [x1, y2, z1],
        [x1, y1, z2],
        [x2, y1, z2],
        [x2, y2, z2],
        [x1, y2, z2]
    ])

    # 12 triangular faces (2 per box face)
    faces = np.array([
        [0, 3, 1], [1, 3, 2],  # bottom
        [0, 4, 7], [0, 7, 3],  # left
        [4, 5, 6], [4, 6, 7],  # top
        [5, 1, 2], [5, 2, 6],  # right
        [2, 3, 6], [3, 7, 6],  # back
        [0, 1, 5], [0, 5, 4]   # front
    ])

    # Create mesh data (triangles with vertices)
    mesh_data = vertices[faces]

    return mesh_data


def merge_stl_meshes(meshes: list[np.ndarray]) -> bytes:
    """
    Merge multiple mesh arrays into a single STL binary format.

    Uses vectorized numpy operations for normals and a structured array
    for single-allocation binary output (~10-20x faster, ~100 MB less peak memory).

    Args:
        meshes: List of mesh arrays (each is Nx3x3 array of triangles)

    Returns:
        Binary STL file content
    """
    if not meshes:
        # Return valid empty STL: 80-byte header + uint32(0) triangle count
        return b' ' * 80 + np.uint32(0).tobytes()

    # Concatenate all meshes into single array, then free source list
    all_triangles = np.concatenate(meshes, axis=0)
    meshes.clear()
    num_triangles = len(all_triangles)

    # Vectorized normal computation
    v1 = all_triangles[:, 0]
    v2 = all_triangles[:, 1]
    v3 = all_triangles[:, 2]
    normals = np.cross(v2 - v1, v3 - v1)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normals = normals / norms

    # Build binary STL in a single structured array allocation
    # STL record: normal(3×f32) + v1(3×f32) + v2(3×f32) + v3(3×f32) + attr(u16)
    record_dtype = np.dtype([
        ('normal', np.float32, (3,)),
        ('v1', np.float32, (3,)),
        ('v2', np.float32, (3,)),
        ('v3', np.float32, (3,)),
        ('attr', np.uint16)
    ])
    records = np.zeros(num_triangles, dtype=record_dtype)
    records['normal'] = normals.astype(np.float32)
    records['v1'] = v1.astype(np.float32)
    records['v2'] = v2.astype(np.float32)
    records['v3'] = v3.astype(np.float32)

    header = b' ' * 80
    count = np.uint32(num_triangles).tobytes()
    return header + count + records.tobytes()


def generate_boxes_batch(
    box_ranges: list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]
) -> np.ndarray:
    """
    Generate multiple 3D box meshes in a single vectorized operation.

    Instead of calling generate_box() N times (each producing a (12,3,3) array),
    this builds all boxes at once, reducing Python object overhead.

    Args:
        box_ranges: List of (xrange, yrange, zrange) tuples

    Returns:
        Numpy array of shape (N*12, 3, 3) containing all triangles
    """
    if not box_ranges:
        return np.zeros((0, 3, 3))

    n = len(box_ranges)

    # Extract min/max for each axis: shape (n,)
    coords = np.array(box_ranges, dtype=np.float64)  # (n, 3, 2)
    x1 = coords[:, 0, 0]
    x2 = coords[:, 0, 1]
    y1 = coords[:, 1, 0]
    y2 = coords[:, 1, 1]
    z1 = coords[:, 2, 0]
    z2 = coords[:, 2, 1]

    # Build 8 vertices per box: shape (n, 8, 3)
    vertices = np.empty((n, 8, 3), dtype=np.float64)
    vertices[:, 0] = np.column_stack([x1, y1, z1])
    vertices[:, 1] = np.column_stack([x2, y1, z1])
    vertices[:, 2] = np.column_stack([x2, y2, z1])
    vertices[:, 3] = np.column_stack([x1, y2, z1])
    vertices[:, 4] = np.column_stack([x1, y1, z2])
    vertices[:, 5] = np.column_stack([x2, y1, z2])
    vertices[:, 6] = np.column_stack([x2, y2, z2])
    vertices[:, 7] = np.column_stack([x1, y2, z2])

    # 12 face triangles (same indices as generate_box)
    face_indices = np.array([
        [0, 3, 1], [1, 3, 2],  # bottom
        [0, 4, 7], [0, 7, 3],  # left
        [4, 5, 6], [4, 6, 7],  # top
        [5, 1, 2], [5, 2, 6],  # right
        [2, 3, 6], [3, 7, 6],  # back
        [0, 1, 5], [0, 5, 4]   # front
    ], dtype=np.int32)

    # Index into vertices: result shape (n, 12, 3, 3)
    triangles = vertices[:, face_indices]

    # Reshape to (n*12, 3, 3)
    return triangles.reshape(-1, 3, 3)


def layer_runs(blend_code: str, z_offset: float, layer_height: float) -> list[tuple[str, float, float]]:
    """(label, z_min, z_max) per run of identical layers: a run such as YYYYY is
    one solid extrusion, not five stacked copies with internal faces."""
    runs = []
    start = 0
    for label, group in itertools.groupby(blend_code):
        length = len(list(group))
        runs.append((label, z_offset + start * layer_height, z_offset + (start + length) * layer_height))
        start += length
    return runs


def get_filename_prefix(colors: Colors) -> str:
    """Use the material code order for exported filenames."""
    return ''.join(colors.get_labels())


def generate_stl_zip(
    color_blocks: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    use_greedy_meshing: bool = True,
    colors: Optional[Colors] = None,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
) -> bytes:
    """
    Generate ZIP file containing merged STL files by primary color

    Args:
        color_blocks: List of color blocks with RGB and pixels
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        use_greedy_meshing: If True, merge adjacent pixels to reduce file size
        colors: Optional Colors instance. If None, uses current global colors.

    Returns:
        ZIP file binary content
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    # Use provided colors or fall back to global state (thread-safe read)
    if colors is not None:
        active_colors = colors
    else:
        with _global_state_lock:
            active_colors = _current_colors

    if active_colors is None:
        raise RuntimeError("No colors provided and no global colors initialized.")

    # Step 1: Initialize primary color mesh map dynamically
    code_mesh_map = {label: [] for label in active_colors.get_labels()}

    # Step 2: Extract all input colors
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]

    # Step 3: Map to blend codes using the shared preview/export mapping path
    # (backing-aware: the printed block participates in the simulation and
    # rides as a trailing suffix on every code)
    result_codes, result_rgbs = map_color_blocks_to_blend_results(
        color_blocks=color_blocks,
        layer_height=layer_height,
        layer_count=layer_count,
        colors=active_colors,
        backing_layers=white_backing_layers,
        backing_mode=backing_mode,
    )

    _log_input_color_brightness(input_colors, "STL")
    _log_blend_code_distribution(result_codes, active_colors.get_labels(), "STL")

    width, height = image_dimensions['width'], image_dimensions['height']
    total_original_boxes = 0
    total_optimized_boxes = 0

    # Complexity guard: enforced on the REAL merged box count, cumulative
    # across color blocks (see settings.stl_max_boxes). The raw pixel × layer
    # count is logged for observability but does not gate the request —
    # mergeable photos must pass.
    estimated_boxes = sum(len(b['pixels']) for b in color_blocks) * layer_count

    def _remaining_box_budget() -> int:
        return max(0, settings.stl_max_boxes - total_optimized_boxes)

    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(active_colors, n_white, backing_mode)
    if n_white > 0:
        logger.info(
            "Printed backing: mode='%s', label='%s', layers=%d (closest %s filament)",
            backing_mode, w_label, n_white, backing_mode,
        )

    logger.info(
        "STL generation: %d color blocks, %d layers, %dx%d image, ~%d estimated boxes",
        len(color_blocks), layer_count, width, height, estimated_boxes
    )

    # Step 4: Generate meshes for each color block
    for idx, color_block in enumerate(color_blocks):
        pixels = color_block['pixels']
        # The mapping result carries the printed backing as a trailing suffix;
        # the backing block itself is a single merged box below — strip the
        # suffix before per-pixel meshing to avoid double geometry.
        blend_code = strip_backing_suffix(result_codes[idx], w_label, n_white)  # e.g., "CCCM"
        runs = layer_runs(blend_code, z_offset, layer_height)

        # The block's footprint is meshed once; each vertical run extrudes it.
        rectangles = None
        if use_greedy_meshing and len(pixels) > 1:
            rectangles = greedy_mesh_2d(
                pixels_to_grid(pixels, width, height),
                max_rectangles=_remaining_box_budget() // max(len(runs), 1),
            )

        for code_char, z_min, z_max in runs:
            if rectangles is not None:
                optimized_boxes = boxes_from_rectangles(rectangles, pixel_size, z_min, z_max)
                total_original_boxes += len(pixels)
                total_optimized_boxes += len(optimized_boxes)
                code_mesh_map[code_char].append(generate_boxes_batch(optimized_boxes))
            else:
                # Original per-pixel box generation
                total_original_boxes += len(pixels)
                total_optimized_boxes += len(pixels)
                if total_optimized_boxes > settings.stl_max_boxes:
                    raise ValueError(
                        f"Request too complex: {total_optimized_boxes:,} boxes after "
                        f"meshing (budget {settings.stl_max_boxes:,}). "
                        f"Reduce image size or colors."
                    )
                box_ranges = [
                    (
                        (pixel['x'] * pixel_size, (pixel['x'] + 1) * pixel_size),
                        (pixel['y'] * pixel_size, (pixel['y'] + 1) * pixel_size),
                        (z_min, z_max)
                    )
                    for pixel in pixels
                ]
                if box_ranges:
                    batch_mesh = generate_boxes_batch(box_ranges)
                    code_mesh_map[code_char].append(batch_mesh)

    # Step 4b: Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        # Merge all backing layers into a single large block to eliminate internal faces
        backing_mesh = generate_box(
            xrange=(0, width * pixel_size),
            yrange=(0, height * pixel_size),
            zrange=(optical_top,
                    optical_top + n_white * layer_height)
        )
        code_mesh_map[w_label].append(backing_mesh)
        logger.info("Added 1 merged white backing block (thickness=%.2f mm) at z=%.2f-%.2f mm",
                     n_white * layer_height, optical_top, optical_top + n_white * layer_height)

    if use_greedy_meshing and total_original_boxes > 0:
        reduction = (1 - total_optimized_boxes / total_original_boxes) * 100
        logger.info(
            "Greedy meshing: %d -> %d boxes (%.1f%% reduction)",
            total_original_boxes, total_optimized_boxes, reduction
        )

    logger.info("Mesh generation complete, merging STL files...")

    # Step 5: Merge meshes by primary color and create STL files
    stl_files = {}
    print_stack = build_print_stack(
        layer_count=layer_count,
        layer_height=layer_height,
        backing_layers=n_white,
        backing_mode=backing_mode,
    )
    physical_height = print_stack["totalHeightMm"]
    prefix = get_filename_prefix(active_colors)

    for code, meshes in code_mesh_map.items():
        if len(meshes) > 0:
            # Merge all meshes for this primary color
            merged_stl = merge_stl_meshes(meshes)

            # Generate filename: PREFIX_208x208x3.36_C.stl
            filename = f"{prefix}_{width}x{height}x{physical_height:.2f}_{code}.stl"

            stl_files[filename] = merged_stl
            logger.info("Merged color '%s': %d bytes", code, len(merged_stl))

    # Step 6: Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, stl_content in stl_files.items():
            zip_file.writestr(filename, stl_content)

    return zip_buffer.getvalue()
