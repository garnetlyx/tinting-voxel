"""
STL generation service with color mapping and mesh merging

Includes optimization via greedy meshing to reduce file sizes.
"""
import itertools
import logging
import threading
import zipfile
from io import BytesIO
from typing import Optional

import numpy as np
import pandas as pd

from config.settings import settings
from core.blend_color import BlendTestGenerator, Color, Colors
from services.mesh_optimizer import generate_optimized_boxes
from services.print_stack import (
    build_print_stack,
    normalize_white_backing_layers,
    resolve_white_backing_label,
)

logger = logging.getLogger(__name__)


# Global reference matrices (initialized on app startup, used as fallback)
_reference_code_matrix = None
_reference_rgb_matrix = None
_blend_generator = None
_current_colors = None
_global_state_lock = threading.Lock()


def _build_code_to_rgb(colors: Colors, layer_count: int, layer_height: float):
    """Blend callable consistent with compute_reference_matrices."""
    generator = BlendTestGenerator(
        colors=colors,
        layer_height=layer_height,
        layer_count_max=layer_count,
        alpha=colors.get_blend_alpha(),
        blend_mode=colors.get_blend_mode(),
    )
    return generator.code_to_rgb


def compute_reference_matrices(
    layer_count: int,
    layer_height: float,
    colors: Colors,
    prune: Optional[bool] = None,
) -> tuple:
    """
    Compute color reference matrices for Beer-Lambert mapping.

    Thread-safe: returns new matrices without modifying global state.

    Args:
        layer_count: Number of layers for color blending
        layer_height: Height of each layer in mm
        colors: Colors instance defining the filament configuration

    Returns:
        Tuple of (code_matrix, rgb_matrix) as DataFrames

    prune:
        None (default) prunes to composition representatives in the translucent
        regime and keeps full enumeration otherwise; False forces the full
        ordered enumeration in every regime (correctness oracle for the
        pruned path). Pruning is never forced outside the translucent regime.

    Raises:
        ValueError: If permutation count exceeds safety limit
    """
    if layer_count <= 0:
        raise ValueError(f"layer_count must be positive, got {layer_count}")
    generator = BlendTestGenerator(
        colors=colors,
        layer_height=layer_height,
        layer_count_max=layer_count,
        alpha=colors.get_blend_alpha(),
        blend_mode=colors.get_blend_mode(),
    )

    items = colors.get_labels()
    if not items:
        raise ValueError("Colors instance has no colors defined")
    max_permutations = 1_000_000
    permutation_count = len(items) ** layer_count

    if prune is True:
        raise ValueError(
            "prune=True is not supported: pruning applies automatically and "
            "only to translucent sets. Use prune=None (automatic) or "
            "prune=False (full-enumeration oracle)."
        )

    from core.stack_prune import composition_codes, is_translucent_set

    translucent = is_translucent_set(colors, require_measured_td=True)
    # Pruning only ever operates in the translucent regime: `prune` may opt
    # OUT (False, the oracle) but can never force an opaque or mixed set onto
    # the composition-pruned path.
    use_prune = translucent and prune is not False
    if use_prune:
        # Translucent regime: one canonical representative per composition
        # (C(N+L-1, L) candidates; see core/stack_prune.py) instead of the
        # full ordered product; order is recovered per match by
        # refine_matches().
        code_list = composition_codes(items, layer_count)
        if len(code_list) > max_permutations:
            raise ValueError(
                f"Too many stack compositions: {len(items)} colors x {layer_count} layers = "
                f"{len(code_list):,}. Maximum allowed is {max_permutations:,}. "
                f"Reduce the number of colors or layers."
            )
        logger.info(
            "Pruned stack candidates: %d compositions of %d colors x %d layers, "
            "%d diverse orderings in matrix (full ordered set would be %d)",
            len(set("".join(sorted(c)) for c in code_list)), len(items), layer_count,
            len(code_list), permutation_count,
        )
    else:
        if permutation_count > max_permutations:
            raise ValueError(
                f"Too many color permutations: {len(items)} colors x {layer_count} layers = "
                f"{permutation_count:,}. Maximum allowed is {max_permutations:,}. "
                f"Reduce the number of colors or layers."
            )
        perms = list(itertools.product(items, repeat=layer_count))
        code_list = [''.join(p) for p in perms]

    rgb_list = [generator.code_to_rgb(code) for code in code_list]

    n = len(code_list)
    rows = int(np.sqrt(n))
    cols = (n + rows - 1) // rows

    # Pad with last valid entry to avoid empty-string codes in nearest-color matching
    pad_count = rows * cols - n
    pad_code = code_list[-1] if code_list else ''
    pad_rgb = rgb_list[-1] if rgb_list else (255, 255, 255)
    code_list_padded = code_list + [pad_code] * pad_count
    rgb_list_padded = rgb_list + [pad_rgb] * pad_count

    code_matrix = [code_list_padded[i*cols:(i+1)*cols] for i in range(rows)]
    rgb_matrix = [rgb_list_padded[i*cols:(i+1)*cols] for i in range(rows)]

    code_df = pd.DataFrame(code_matrix)
    rgb_df = pd.DataFrame(rgb_matrix)

    logger.info(
        "Computed reference matrices: %d colors, %d candidates%s",
        len(items), len(code_list),
        " (composition-pruned)" if use_prune else "",
    )
    return code_df, rgb_df


def map_color_blocks_to_blend_results(
    color_blocks: list[dict],
    layer_height: float,
    layer_count: int,
    colors: Colors,
) -> tuple[list[str], list[tuple[int, int, int]]]:
    """
    Map source RGB blocks to nearest printable blend codes and RGBs.

    Uses the same reference matrices and LAB nearest-neighbor matching as STL export.
    """
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count,
        layer_height,
        colors,
    )
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
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
        code_to_rgb=_build_code_to_rgb(colors, layer_count, layer_height),
    )
    normalized_rgbs = [
        tuple(int(channel) for channel in np.asarray(rgb).tolist())
        for rgb in result_rgbs
    ]
    return result_codes, normalized_rgbs


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
        colors: Optional Colors instance. If None, uses default Phase 6 CMYW.
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
            alpha=colors.get_blend_alpha(),
            blend_mode=colors.get_blend_mode(),
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


def _find_white_label(colors: Colors) -> Optional[str]:
    """
    Find the white filament label in a Colors instance.

    Checks for label 'W' first, then falls back to any color with hex '#FFFFFF'.

    Returns:
        The label string (e.g. 'W') or None if no white filament found.
    """
    labels = colors.get_labels()
    if 'W' in labels:
        return 'W'
    for label in labels:
        if colors[label].hex.upper() == '#FFFFFF':
            return label
    return None


def _calculate_white_layers(unique_codes, layer_height, colors, alpha=12.0):
    """Return 0-5 white backing layers based on maximum transmittance.

    Calculates the maximum light remaining after passing through the optical
    stack for all unique blend codes. More transparent stacks need thicker
    white backing to provide adequate reflection.

    Args:
        unique_codes: set of blend code strings, e.g. {"WWWW", "CCWW"}
        layer_height: layer height in mm
        colors: Colors instance with filament definitions
        alpha: absorption coefficient for Beer-Lambert model

    Returns:
        Number of white backing layers (0-5)
    """
    max_remain = 0.0
    for code in unique_codes:
        remain = 1.0
        for c in code:
            remain *= Color.get_transmission_rate(layer_height, colors[c].td, alpha)
        if remain > max_remain:
            max_remain = remain
    if max_remain < 0.01:
        return 0
    return max(1, int(max_remain * 5 + 0.5))


def get_filename_prefix(colors: Colors) -> str:
    """
    Generate filename prefix from color labels.

    Maintains backward compatibility: CMYW produces "CMYW" prefix.

    Args:
        colors: Colors instance

    Returns:
        String prefix for filenames
    """
    labels = colors.get_labels()
    # Backward compatibility: if labels are exactly C, M, Y, W in any order,
    # and we have exactly 4 colors, use CMYW for consistency
    if set(labels) == {'C', 'M', 'Y', 'W'} and len(labels) == 4:
        return "CMYW"
    return ''.join(labels)


def generate_stl_zip(
    color_blocks: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    use_greedy_meshing: bool = True,
    colors: Optional[Colors] = None,
    white_backing_layers: int = 1,
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
    result_codes, result_rgbs = map_color_blocks_to_blend_results(
        color_blocks=color_blocks,
        layer_height=layer_height,
        layer_count=layer_count,
        colors=active_colors,
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

    n_white = normalize_white_backing_layers(white_backing_layers)
    w_label = resolve_white_backing_label(active_colors, n_white)
    if n_white > 0:
        logger.info("White backing: label='%s', n_white=%d (configured)", w_label, n_white)

    logger.info(
        "STL generation: %d color blocks, %d layers, %dx%d image, ~%d estimated boxes",
        len(color_blocks), layer_count, width, height, estimated_boxes
    )

    # Step 4: Generate meshes for each color block
    for idx, color_block in enumerate(color_blocks):
        pixels = color_block['pixels']
        blend_code = result_codes[idx]  # e.g., "CCCM"

        # Group contiguous identical colors vertically to eliminate internal faces
        start_idx = 0
        for code_char, group in itertools.groupby(blend_code):
            group_len = len(list(group))
            z_min = z_offset + start_idx * layer_height
            z_max = z_offset + (start_idx + group_len) * layer_height
            start_idx += group_len

            if use_greedy_meshing and len(pixels) > 1:
                # Use greedy meshing to merge adjacent pixels
                optimized_boxes = generate_optimized_boxes(
                    pixels=pixels,
                    width=width,
                    height=height,
                    pixel_size=pixel_size,
                    z_min=z_min,
                    z_max=z_max,
                    max_rectangles=_remaining_box_budget(),
                )
                total_original_boxes += len(pixels)
                total_optimized_boxes += len(optimized_boxes)

                # Batch-generate all box meshes at once
                batch_mesh = generate_boxes_batch(optimized_boxes)
                code_mesh_map[code_char].append(batch_mesh)
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
        white_backing_layers=n_white,
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
