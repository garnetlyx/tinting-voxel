"""
3MF generation service: one object with a part per filament.

Each filament's layers become one colored part of a single object
(services/threemf_writer.py), which slicers like Bambu Studio assign to
filament slots.
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import logging
import re
from typing import Optional, Sequence

import numpy as np

from core.blend_color import Colors
from config.settings import settings
from services.label_map import EMPTY
from services.mesh_optimizer import BoxRange, boxes_from_rectangles, greedy_mesh_2d
from services.threemf_writer import Part, write_3mf
from services.print_stack import (
    PRINT_BACKGROUND_RGB,
    backing_suffix,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)
from services.stl_generator import (
    block_box_runs,
    compute_reference_matrices,
    layer_runs,
    map_color_blocks_to_blend_results,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.vector_processor import finalize_vector_partition

logger = logging.getLogger(__name__)

def _package(code_mesh_map: dict[str, list[list[BoxRange]]], colors: Colors,
             color_hex_map: Optional[dict]) -> bytes:
    """One object with a part per filament, colored by the filament's hex."""
    hex_by_label = color_hex_map or {}
    parts = [
        Part(
            name=colors[label].name,
            color=hex_by_label.get(label, colors[label].hex),
            boxes=[box for batch in batches for box in batch],
        )
        for label, batches in code_mesh_map.items()
    ]
    result = write_3mf(parts, object_name="Tinting Voxel")
    logger.info("Generated 3MF file: %d filament parts, %d bytes", sum(bool(p.boxes) for p in parts), len(result))
    return result


def generate_3mf(
    color_blocks: list[dict],
    labels: np.ndarray,
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    use_greedy_meshing: bool = True,
    colors: Optional[Colors] = None,
    color_hex_map: Optional[dict] = None,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_filament: Optional[str] = None,
    white_point: Optional[Sequence[float]] = None,
) -> bytes:
    """
    Generate a single 3MF file with color-separated objects.

    Each filament color layer is a separate named object in the 3MF,
    which slicers can assign to different extruders.

    Args:
        color_blocks: Color blocks (RGB); block i prints where labels == i
        labels: (height, width) label map of the model grid (services/label_map.py)
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        use_greedy_meshing: If True, merge adjacent pixels
        colors: Optional Colors instance
        color_hex_map: Optional dict mapping label -> hex color for visual colors

    Returns:
        3MF file binary content
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    if colors is None:
        raise ValueError("Colors instance is required for 3MF generation")

    # Validate color_hex_map values upfront
    if color_hex_map:
        for label, hex_color in color_hex_map.items():
            if not re.match(r'^#[0-9a-fA-F]{6}$', hex_color):
                raise ValueError(
                    f"Invalid hex color '{hex_color}' for label '{label}'"
                )

    # Box ranges per filament until packaging (services/threemf_writer.py).
    code_mesh_map: dict[str, list[list[BoxRange]]] = {label: [] for label in colors.get_labels()}

    # Map input colors to blend codes (shared with processing and STL export);
    # codes carry the printed backing as a trailing suffix.
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
    result_codes, _ = map_color_blocks_to_blend_results(
        color_blocks=color_blocks,
        layer_height=layer_height,
        layer_count=layer_count,
        colors=colors,
        backing_layers=white_backing_layers,
        backing_filament=backing_filament,
        white_point=white_point,
    )

    _log_input_color_brightness(input_colors, "3MF")
    _log_blend_code_distribution(result_codes, colors.get_labels(), "3MF")

    height, width = labels.shape
    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(colors, n_white, backing_filament)
    if n_white > 0:
        logger.info("3MF: printed backing label='%s', layers=%d", w_label, n_white)

    # The raw pixel x layer count is logged for observability; the complexity
    # guard applies to the real merged box count (block_box_runs).
    estimated_boxes = int((labels != EMPTY).sum()) * layer_count
    logger.info(
        "3MF generation: %d color blocks, %d layers, %dx%d image, ~%d estimated boxes",
        len(color_blocks), layer_count, width, height, estimated_boxes
    )

    # Backing suffix -> single merged block below; strip before meshing.
    block_codes = [strip_backing_suffix(code, w_label, n_white) for code in result_codes]
    for code_char, boxes, _cells in block_box_runs(labels, block_codes, pixel_size, layer_height, use_greedy_meshing):
        code_mesh_map[code_char].append(boxes)

    # Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        code_mesh_map[w_label].append([(
            (0, width * pixel_size),
            (0, height * pixel_size),
            (optical_top, optical_top + n_white * layer_height),
        )])
        logger.info("3MF: added 1 merged white backing block at z=%.2f-%.2f mm",
                     optical_top, optical_top + n_white * layer_height)

    return _package(code_mesh_map, colors, color_hex_map)


def generate_svg_3mf(
    vector_results: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    colors: Optional[Colors] = None,
    color_hex_map: Optional[dict] = None,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_filament: Optional[str] = None,
    detail_size: Optional[float] = None,
    white_point: Optional[Sequence[float]] = None,
) -> bytes:
    """
    Generate a single 3MF file from SVG vector contours with color-separated objects.

    Args:
        vector_results: List of dicts with 'color' (RGB tuple) and 'regions' keys
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        colors: Colors instance (required)
        color_hex_map: Optional dict mapping label -> hex color for visual colors
        detail_size: Minimum printable feature width in mm.

    Returns:
        3MF file binary content
    """
    if not vector_results:
        raise ValueError("No vector results provided")

    if colors is None:
        raise ValueError("Colors instance is required for 3MF generation")

    if color_hex_map:
        for label, hex_color in color_hex_map.items():
            if not re.match(r'^#[0-9a-fA-F]{6}$', hex_color):
                raise ValueError(
                    f"Invalid hex color '{hex_color}' for label '{label}'"
                )

    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count, layer_height, colors, n_targets=len(vector_results),
        backing_layers=white_backing_layers, backing_filament=backing_filament,
    )

    labels = colors.get_labels()
    code_mesh_map: dict[str, list[list[BoxRange]]] = {label: [] for label in labels}

    input_colors = [result['color'] for result in vector_results]
    # Map with order refinement for composition-pruned translucent sets
    # (same as the pixel STL/3MF paths); codes carry the backing suffix.
    from services.image_processor import _map_and_refine
    _b_label = resolve_backing_label(colors, white_backing_layers, backing_filament)
    _b_suffix = backing_suffix(_b_label, white_backing_layers)
    _b_boundary = PRINT_BACKGROUND_RGB if _b_suffix else None
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix,
        colors, layer_count, layer_height,
        backing_suffix=_b_suffix, background_rgb=_b_boundary, white_point=white_point,
    )

    _log_input_color_brightness(input_colors, "SVG-3MF")
    _log_blend_code_distribution(result_codes, labels, "SVG-3MF")

    width = image_dimensions['width']
    height = image_dimensions['height']
    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(colors, n_white, backing_filament)
    if n_white > 0:
        logger.info("SVG-3MF: printed backing label='%s', layers=%d", w_label, n_white)

    total_optimized_boxes = 0
    partition = finalize_vector_partition(
        vector_results, image_dimensions, pixel_size, detail_size,
    )

    def _remaining_box_budget() -> int:
        return max(0, settings.stl_max_boxes - total_optimized_boxes)

    for idx, result in enumerate(vector_results):
        region_grid = partition == idx
        if not region_grid.any():
            continue
        blend_code = strip_backing_suffix(result_codes[idx], w_label, n_white)
        runs = layer_runs(blend_code, z_offset, layer_height)

        # The region is meshed once; each vertical run extrudes it.
        rectangles = greedy_mesh_2d(
            region_grid, max_rectangles=_remaining_box_budget() // max(len(runs), 1),
        )
        for code_char, z_min, z_max in runs:
            boxes = boxes_from_rectangles(rectangles, pixel_size, z_min, z_max)
            if boxes:
                total_optimized_boxes += len(boxes)
                code_mesh_map[code_char].append(boxes)

    # Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        code_mesh_map[w_label].append([(
            (0, width * pixel_size),
            (0, height * pixel_size),
            (optical_top, optical_top + n_white * layer_height),
        )])
        logger.info("SVG-3MF: added 1 merged white backing block at z=%.2f-%.2f mm",
                     optical_top, optical_top + n_white * layer_height)

    return _package(code_mesh_map, colors, color_hex_map)
