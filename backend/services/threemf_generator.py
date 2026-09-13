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
    normalize_white_backing_layers,
    resolve_white_backing_label,
)
from services.stl_generator import (
    compute_reference_matrices,
    generate_box,
    generate_boxes_batch,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.mesh_optimizer import generate_optimized_boxes_from_grid
from services.vector_processor import normalize_regions, render_region_mask

logger = logging.getLogger(__name__)


def _triangles_to_trimesh(mesh_arrays: list[np.ndarray], color_rgb: tuple = None) -> trimesh.Trimesh:
    """
    Convert a list of triangle arrays (from generate_box) into a trimesh.Trimesh.

    Args:
        mesh_arrays: List of Nx3x3 numpy arrays (triangles × vertices × xyz)
        color_rgb: Optional (R, G, B) tuple in 0-255 range for visual color

    Returns:
        trimesh.Trimesh object
    """
    if not mesh_arrays:
        return trimesh.Trimesh()

    all_triangles = np.concatenate(mesh_arrays, axis=0)
    mesh_arrays.clear()  # free source arrays for GC
    num_triangles = all_triangles.shape[0]

    # Build vertex and face arrays from triangle soup
    vertices = all_triangles.reshape(-1, 3)
    faces = np.arange(num_triangles * 3).reshape(-1, 3)

    # process=False skips full processing; merge_vertices() deduplicates vertices
    # to fix non-manifold edges while avoiding expensive winding/degenerate checks
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.merge_vertices()

    if color_rgb:
        r, g, b = color_rgb
        mesh.visual.face_colors = np.array([r, g, b, 255], dtype=np.uint8)

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

    # Compute reference matrices locally (thread-safe)
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count, layer_height, colors, n_targets=len(color_blocks)
    )

    # Initialize per-color mesh arrays
    labels = colors.get_labels()
    code_mesh_map: dict[str, list[np.ndarray]] = {label: [] for label in labels}

    # Map input colors to blend codes (with order refinement for pruned sets)
    from services.image_processor import _map_and_refine
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix, colors, layer_count, layer_height,
    )

    _log_input_color_brightness(input_colors, "3MF")
    _log_blend_code_distribution(result_codes, labels, "3MF")

    width, height = image_dimensions['width'], image_dimensions['height']
    z_offset = 0.0

    n_white = normalize_white_backing_layers(white_backing_layers)
    w_label = resolve_white_backing_label(colors, n_white)
    if n_white > 0:
        logger.info("3MF: white backing label='%s', n_white=%d", w_label, n_white)

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
        blend_code = result_codes[idx]

        for z_idx, code_char in enumerate(blend_code):
            z_min = z_offset + z_idx * layer_height
            z_max = z_offset + (z_idx + 1) * layer_height

            if use_greedy_meshing and len(pixels) > 1:
                optimized_boxes = generate_optimized_boxes(
                    pixels=pixels, width=width, height=height,
                    pixel_size=pixel_size, z_min=z_min, z_max=z_max,
                    max_rectangles=_remaining_box_budget(),
                )
                total_optimized_boxes += len(optimized_boxes)
                batch_mesh = generate_boxes_batch(optimized_boxes)
                code_mesh_map[code_char].append(batch_mesh)
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
                    batch_mesh = generate_boxes_batch(box_ranges)
                    code_mesh_map[code_char].append(batch_mesh)

    # Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        for i in range(n_white):
            backing_mesh = generate_box(
                xrange=(0, width * pixel_size),
                yrange=(0, height * pixel_size),
                zrange=(optical_top + i * layer_height,
                        optical_top + (i + 1) * layer_height)
            )
            code_mesh_map[w_label].append(backing_mesh)
        logger.info("3MF: added %d white backing layers at z=%.2f-%.2f mm",
                     n_white, optical_top, optical_top + n_white * layer_height)

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

        mesh_obj = _triangles_to_trimesh(mesh_arrays, color_rgb=rgb)
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
    code_mesh_map: dict[str, list[np.ndarray]] = {label: [] for label in labels}

    input_colors = [result['color'] for result in vector_results]
    # Map with order refinement for composition-pruned translucent sets
    # (same as the pixel STL/3MF paths).
    from services.image_processor import _map_and_refine
    result_codes, _ = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix,
        colors, layer_count, layer_height,
    )

    _log_input_color_brightness(input_colors, "SVG-3MF")
    _log_blend_code_distribution(result_codes, labels, "SVG-3MF")

    width = image_dimensions['width']
    height = image_dimensions['height']
    z_offset = 0.0

    n_white = normalize_white_backing_layers(white_backing_layers)
    w_label = resolve_white_backing_label(colors, n_white)
    if n_white > 0:
        logger.info("SVG-3MF: white backing label='%s', n_white=%d", w_label, n_white)

    for idx, result in enumerate(vector_results):
        regions = normalize_regions(result)
        region_grid = render_region_mask(regions, width=width, height=height)
        if not region_grid.any():
            continue
        blend_code = result_codes[idx]

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
                code_mesh_map[code_char].append(generate_boxes_batch(boxes))

    # Add white backing above optical layers (reflector behind colors)
    if n_white > 0:
        optical_top = z_offset + layer_count * layer_height
        for i in range(n_white):
            backing_mesh = generate_box(
                xrange=(0, width * pixel_size),
                yrange=(0, height * pixel_size),
                zrange=(optical_top + i * layer_height,
                        optical_top + (i + 1) * layer_height)
            )
            code_mesh_map[w_label].append(backing_mesh)
        logger.info("SVG-3MF: added %d white backing layers at z=%.2f-%.2f mm",
                     n_white, optical_top, optical_top + n_white * layer_height)

    buf = BytesIO()
    scene.export(buf, file_type='3mf')
    result = buf.getvalue()

    logger.info(
        "Generated SVG 3MF file: %d objects, %d bytes",
        len(scene.geometry), len(result)
    )

    return result
