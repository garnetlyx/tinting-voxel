"""
3MF generation service - produces a single 3MF file with color-separated objects.

Uses trimesh for 3MF export. Each filament color layer becomes a separate
object in the 3MF file, which slicers like Bambu Studio can assign to
different extruders.
"""
import itertools
import logging
import re
from io import BytesIO
from typing import Optional

import numpy as np
import trimesh

from core.blend_color import Color, Colors
from config.settings import settings
from services.mesh_optimizer import generate_optimized_boxes
from services.print_stack import (
    backing_boundary_rgb,
    backing_suffix,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)
from services.stl_generator import (
    compute_reference_matrices,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.mesh_optimizer import generate_optimized_boxes_from_grid
from services.vector_processor import normalize_regions, render_region_mask

logger = logging.getLogger(__name__)


BoxRange = tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
]


def _boxes_to_trimesh(
    box_batches: list[list[BoxRange]],
    color_rgb: Optional[tuple[int, int, int]] = None,
) -> trimesh.Trimesh:
    """Build an indexed mesh directly from compact box ranges."""
    box_count = sum(len(batch) for batch in box_batches)
    if box_count == 0:
        return trimesh.Trimesh()

    vertices = np.empty((box_count * 8, 3), dtype=np.float32)
    faces = np.empty((box_count * 12, 3), dtype=np.int64)
    local_faces = np.array([
        [0, 3, 1], [1, 3, 2],
        [0, 4, 7], [0, 7, 3],
        [4, 5, 6], [4, 6, 7],
        [5, 1, 2], [5, 2, 6],
        [2, 3, 6], [3, 7, 6],
        [0, 1, 5], [0, 5, 4],
    ], dtype=np.int64)

    box_offset = 0
    for batch in box_batches:
        if not batch:
            continue
        coords = np.asarray(batch, dtype=np.float32)
        count = len(batch)
        x1, x2 = coords[:, 0, 0], coords[:, 0, 1]
        y1, y2 = coords[:, 1, 0], coords[:, 1, 1]
        z1, z2 = coords[:, 2, 0], coords[:, 2, 1]
        batch_vertices = np.empty((count, 8, 3), dtype=np.float32)
        batch_vertices[:, 0] = np.column_stack((x1, y1, z1))
        batch_vertices[:, 1] = np.column_stack((x2, y1, z1))
        batch_vertices[:, 2] = np.column_stack((x2, y2, z1))
        batch_vertices[:, 3] = np.column_stack((x1, y2, z1))
        batch_vertices[:, 4] = np.column_stack((x1, y1, z2))
        batch_vertices[:, 5] = np.column_stack((x2, y1, z2))
        batch_vertices[:, 6] = np.column_stack((x2, y2, z2))
        batch_vertices[:, 7] = np.column_stack((x1, y2, z2))

        vertex_start = box_offset * 8
        face_start = box_offset * 12
        vertices[vertex_start:vertex_start + count * 8] = batch_vertices.reshape(-1, 3)
        offsets = (np.arange(count, dtype=np.int64) * 8 + vertex_start)[:, None, None]
        faces[face_start:face_start + count * 12] = (local_faces[None, :, :] + offsets).reshape(-1, 3)
        box_offset += count

    box_batches.clear()
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.merge_vertices()

    if color_rgb:
        mesh.visual.face_colors = np.array([*color_rgb, 255], dtype=np.uint8)

    return mesh


def generate_3mf(
    color_blocks: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    use_greedy_meshing: bool = True,
    colors: Optional[Colors] = None,
    color_hex_map: Optional[dict] = None,
    white_backing_layers: int = 1,
    backing_mode: str = 'white',
) -> bytes:
    """
    Generate a single 3MF file with color-separated objects.

    Each filament color layer is a separate named object in the 3MF,
    which slicers can assign to different extruders.

    Args:
        color_blocks: List of color blocks with RGB and pixels
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
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

    # Compute reference matrices locally (thread-safe, backing-aware)
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count, layer_height, colors, n_targets=len(color_blocks),
        backing_layers=white_backing_layers, backing_mode=backing_mode,
    )

    # Keep compact box ranges until the final indexed trimesh conversion.
    labels = colors.get_labels()
    code_mesh_map: dict[str, list[list[BoxRange]]] = {label: [] for label in labels}

    # Map input colors to blend codes (with order refinement for pruned sets);
    # codes carry the printed backing as a trailing suffix.
    from services.image_processor import _map_and_refine
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
    _b_label = resolve_backing_label(colors, white_backing_layers, backing_mode)
    _b_suffix = backing_suffix(_b_label, white_backing_layers)
    _b_boundary = backing_boundary_rgb(backing_mode) if _b_suffix else None
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix, colors, layer_count, layer_height,
        backing_suffix=_b_suffix, background_rgb=_b_boundary,
    )

    _log_input_color_brightness(input_colors, "3MF")
    _log_blend_code_distribution(result_codes, labels, "3MF")

    width, height = image_dimensions['width'], image_dimensions['height']
    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(colors, n_white, backing_mode)
    if n_white > 0:
        logger.info("3MF: printed backing mode='%s', label='%s', layers=%d", backing_mode, w_label, n_white)

    # Complexity guard: enforced on the REAL merged box count (see
    # settings.stl_max_boxes); the raw estimate is logged for observability.
    estimated_boxes = sum(len(b['pixels']) for b in color_blocks) * layer_count
    total_optimized_boxes = 0

    def _remaining_box_budget() -> int:
        return max(0, settings.stl_max_boxes - total_optimized_boxes)

    logger.info(
        "3MF generation: %d color blocks, %d layers, %dx%d image, ~%d estimated boxes",
        len(color_blocks), layer_count, width, height, estimated_boxes
    )

    # Generate meshes per color block
    for idx, color_block in enumerate(color_blocks):
        pixels = color_block['pixels']
        # Backing suffix -> single merged block below; strip before meshing.
        blend_code = strip_backing_suffix(result_codes[idx], w_label, n_white)

        # A run such as YYYYY is one solid extrusion, not five stacked
        # copies of the same surface mesh. This matches the STL path and
        # removes internal horizontal faces before trimesh export.
        start_idx = 0
        for code_char, group in itertools.groupby(blend_code):
            group_len = len(list(group))
            z_min = z_offset + start_idx * layer_height
            z_max = z_offset + (start_idx + group_len) * layer_height
            start_idx += group_len

            if use_greedy_meshing and len(pixels) > 1:
                optimized_boxes = generate_optimized_boxes(
                    pixels=pixels, width=width, height=height,
                    pixel_size=pixel_size, z_min=z_min, z_max=z_max,
                    max_rectangles=_remaining_box_budget(),
                )
                total_optimized_boxes += len(optimized_boxes)
                code_mesh_map[code_char].append(optimized_boxes)
            else:
                box_ranges = [
                    (
                        (pixel['x'] * pixel_size, (pixel['x'] + 1) * pixel_size),
                        (pixel['y'] * pixel_size, (pixel['y'] + 1) * pixel_size),
                        (z_min, z_max)
                    )
                    for pixel in pixels
                ]
                if box_ranges:
                    total_optimized_boxes += len(box_ranges)
                    if total_optimized_boxes > settings.stl_max_boxes:
                        raise ValueError(
                            f"Request too complex: {total_optimized_boxes:,} boxes after "
                            f"meshing (budget {settings.stl_max_boxes:,}). "
                            f"Reduce image size or colors."
                        )
                    code_mesh_map[code_char].append(box_ranges)

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

    logger.info("Mesh generation complete, converting to trimesh objects...")

    # Convert to trimesh Scene with named objects
    scene = trimesh.Scene()

    for label, mesh_arrays in code_mesh_map.items():
        if not mesh_arrays:
            continue

        # Resolve visual color from hex map
        rgb = None
        if color_hex_map and label in color_hex_map:
            hex_color = color_hex_map[label]
            rgb = (
                int(hex_color[1:3], 16),
                int(hex_color[3:5], 16),
                int(hex_color[5:7], 16),
            )

        mesh_obj = _boxes_to_trimesh(mesh_arrays, color_rgb=rgb)
        geom_name = f"color_{label}"
        scene.add_geometry(mesh_obj, node_name=geom_name, geom_name=geom_name)
        logger.info("Converted color '%s': %d triangles", label, len(mesh_obj.faces))

    # Export as 3MF
    logger.info("Exporting 3MF file with %d objects...", len(scene.geometry))
    buf = BytesIO()
    scene.export(buf, file_type='3mf')
    result = buf.getvalue()

    logger.info(
        "Generated 3MF file: %d objects, %d bytes",
        len(scene.geometry), len(result)
    )

    return result


def generate_svg_3mf(
    vector_results: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    colors: Optional[Colors] = None,
    color_hex_map: Optional[dict] = None,
    white_backing_layers: int = 1,
    backing_mode: str = 'white',
) -> bytes:
    """
    Generate a single 3MF file from SVG vector contours with color-separated objects.

    Args:
        vector_results: List of dicts with 'color' (RGB tuple) and 'polygons' keys
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        colors: Colors instance (required)
        color_hex_map: Optional dict mapping label -> hex color for visual colors

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
        layer_count, layer_height, colors, n_targets=len(vector_results)
    )

    labels = colors.get_labels()
    code_mesh_map: dict[str, list[list[BoxRange]]] = {label: [] for label in labels}

    input_colors = [result['color'] for result in vector_results]
    # Map with order refinement for composition-pruned translucent sets
    # (same as the pixel STL/3MF paths); codes carry the backing suffix.
    from services.image_processor import _map_and_refine
    _b_label = resolve_backing_label(colors, white_backing_layers, backing_mode)
    _b_suffix = backing_suffix(_b_label, white_backing_layers)
    _b_boundary = backing_boundary_rgb(backing_mode) if _b_suffix else None
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix,
        colors, layer_count, layer_height,
        backing_suffix=_b_suffix, background_rgb=_b_boundary,
    )

    _log_input_color_brightness(input_colors, "SVG-3MF")
    _log_blend_code_distribution(result_codes, labels, "SVG-3MF")

    width = image_dimensions['width']
    height = image_dimensions['height']
    z_offset = 0.0

    n_white = normalize_backing_layers(white_backing_layers)
    w_label = resolve_backing_label(colors, n_white, backing_mode)
    if n_white > 0:
        logger.info("SVG-3MF: printed backing mode='%s', label='%s', layers=%d", backing_mode, w_label, n_white)

    total_optimized_boxes = 0

    def _remaining_box_budget() -> int:
        return max(0, settings.stl_max_boxes - total_optimized_boxes)

    for idx, result in enumerate(vector_results):
        regions = normalize_regions(result)
        region_grid = render_region_mask(regions, width=width, height=height)
        if not region_grid.any():
            continue
        blend_code = strip_backing_suffix(result_codes[idx], w_label, n_white)

        start_idx = 0
        for code_char, group in itertools.groupby(blend_code):
            group_len = len(list(group))
            z_min = z_offset + start_idx * layer_height
            z_max = z_offset + (start_idx + group_len) * layer_height
            start_idx += group_len

            boxes = generate_optimized_boxes_from_grid(
                grid=region_grid,
                pixel_size=pixel_size,
                z_min=z_min,
                z_max=z_max,
                max_rectangles=_remaining_box_budget(),
            )
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

    scene = trimesh.Scene()
    for label, mesh_arrays in code_mesh_map.items():
        if not mesh_arrays:
            continue
        rgb = None
        if color_hex_map and label in color_hex_map:
            hex_color = color_hex_map[label]
            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        mesh_obj = _boxes_to_trimesh(mesh_arrays, color_rgb=rgb)
        geom_name = f"color_{label}"
        scene.add_geometry(mesh_obj, node_name=geom_name, geom_name=geom_name)

    buf = BytesIO()
    scene.export(buf, file_type='3mf')
    result = buf.getvalue()

    logger.info(
        "Generated SVG 3MF file: %d objects, %d bytes",
        len(scene.geometry), len(result)
    )

    return result
