"""
3MF generation service - produces a single 3MF file with color-separated objects.

Uses trimesh for 3MF export. Each filament color layer becomes a separate
object in the 3MF file, which slicers like Bambu Studio can assign to
different extruders.
"""
import logging
import re
from io import BytesIO
from typing import Optional

import numpy as np
import trimesh

from core.blend_color import Color, Colors
from services.mesh_optimizer import generate_optimized_boxes
from services.stl_generator import (
    compute_reference_matrices,
    generate_box,
    generate_boxes_batch,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.svg_stl_generator import generate_polygon_mesh

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
    base_plate_thickness: float = 0.0,
    color_hex_map: Optional[dict] = None,
    double_sided: bool = False,
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
        base_plate_thickness: Thickness of base plate in mm
        color_hex_map: Optional dict mapping label -> hex color for visual colors
        double_sided: If True, generate mirrored back side layers on top

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
        layer_count, layer_height, colors
    )

    # Initialize per-color mesh arrays
    labels = colors.get_labels()
    code_mesh_map: dict[str, list[np.ndarray]] = {label: [] for label in labels}

    # Map input colors to blend codes
    input_colors = [(block['r'], block['g'], block['b']) for block in color_blocks]
    result_codes, _ = Color.map_to_nearest_color(
        input_colors, ref_code_matrix, ref_rgb_matrix
    )

    _log_input_color_brightness(input_colors, "3MF")
    _log_blend_code_distribution(result_codes, labels, "3MF")

    width, height = image_dimensions['width'], image_dimensions['height']
    z_offset = base_plate_thickness if base_plate_thickness > 0 else 0.0

    # Complexity guard
    estimated_boxes = sum(len(b['pixels']) for b in color_blocks) * layer_count
    if estimated_boxes > 5_000_000:
        raise ValueError(
            f"Request too complex: ~{estimated_boxes:,} estimated boxes. "
            f"Reduce image size or colors."
        )

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
                    pixel_size=pixel_size, z_min=z_min, z_max=z_max
                )
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

    # Generate back-side (mirrored) layers if double-sided
    if double_sided:
        front_top = z_offset + layer_count * layer_height
        for idx, color_block in enumerate(color_blocks):
            pixels = color_block['pixels']
            blend_code = result_codes[idx]

            mirrored_pixels = [
                {'x': width - 1 - p['x'], 'y': p['y']}
                for p in pixels
            ]

            for z_idx, code_char in enumerate(reversed(blend_code)):
                z_min = front_top + z_idx * layer_height
                z_max = front_top + (z_idx + 1) * layer_height

                if use_greedy_meshing and len(mirrored_pixels) > 1:
                    optimized_boxes = generate_optimized_boxes(
                        pixels=mirrored_pixels, width=width, height=height,
                        pixel_size=pixel_size, z_min=z_min, z_max=z_max
                    )
                    batch_mesh = generate_boxes_batch(optimized_boxes)
                    code_mesh_map[code_char].append(batch_mesh)
                else:
                    box_ranges = [
                        (
                            (p['x'] * pixel_size, (p['x'] + 1) * pixel_size),
                            (p['y'] * pixel_size, (p['y'] + 1) * pixel_size),
                            (z_min, z_max)
                        )
                        for p in mirrored_pixels
                    ]
                    if box_ranges:
                        batch_mesh = generate_boxes_batch(box_ranges)
                        code_mesh_map[code_char].append(batch_mesh)

        logger.info("Generated double-sided 3MF: front + mirrored back")

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
        scene.add_geometry(mesh_obj, node_name=f"color_{label}")
        logger.info("Converted color '%s': %d triangles", label, len(mesh_obj.faces))

    # Add base plate
    if base_plate_thickness > 0:
        base_mesh_data = generate_box(
            xrange=(0, width * pixel_size),
            yrange=(0, height * pixel_size),
            zrange=(0, base_plate_thickness)
        )
        base_obj = _triangles_to_trimesh([base_mesh_data])
        scene.add_geometry(base_obj, node_name="base_plate")

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
    base_plate_thickness: float = 0.0,
    color_hex_map: Optional[dict] = None,
    double_sided: bool = False,
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
        base_plate_thickness: Thickness of base plate in mm
        color_hex_map: Optional dict mapping label -> hex color for visual colors
        double_sided: If True, generate mirrored back side layers on top

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
        layer_count, layer_height, colors
    )

    labels = colors.get_labels()
    code_mesh_map: dict[str, list[np.ndarray]] = {label: [] for label in labels}

    input_colors = [result['color'] for result in vector_results]
    result_codes, _ = Color.map_to_nearest_color(
        input_colors, ref_code_matrix, ref_rgb_matrix
    )

    _log_input_color_brightness(input_colors, "SVG-3MF")
    _log_blend_code_distribution(result_codes, labels, "SVG-3MF")

    width = image_dimensions['width']
    height = image_dimensions['height']
    z_offset = base_plate_thickness if base_plate_thickness > 0 else 0.0

    for idx, result in enumerate(vector_results):
        polygons = result['polygons']
        blend_code = result_codes[idx]

        for z_idx, code_char in enumerate(blend_code):
            z_min = z_offset + z_idx * layer_height
            z_max = z_offset + (z_idx + 1) * layer_height

            for polygon in polygons:
                if len(polygon) < 3:
                    continue
                mesh = generate_polygon_mesh(
                    polygon=polygon, z_min=z_min, z_max=z_max,
                    pixel_size=pixel_size
                )
                if len(mesh) > 0:
                    code_mesh_map[code_char].append(mesh)

    if double_sided:
        front_top = z_offset + layer_count * layer_height
        for idx, result in enumerate(vector_results):
            polygons = result['polygons']
            blend_code = result_codes[idx]

            mirrored_polygons = [
                [(width - 1 - x, y) for x, y in polygon]
                for polygon in polygons
            ]

            for z_idx, code_char in enumerate(reversed(blend_code)):
                z_min = front_top + z_idx * layer_height
                z_max = front_top + (z_idx + 1) * layer_height

                for polygon in mirrored_polygons:
                    if len(polygon) < 3:
                        continue
                    mesh = generate_polygon_mesh(
                        polygon=polygon, z_min=z_min, z_max=z_max,
                        pixel_size=pixel_size
                    )
                    if len(mesh) > 0:
                        code_mesh_map[code_char].append(mesh)

        logger.info("Generated double-sided SVG 3MF: front + mirrored back")

    scene = trimesh.Scene()

    for label, mesh_arrays in code_mesh_map.items():
        if not mesh_arrays:
            continue

        rgb = None
        if color_hex_map and label in color_hex_map:
            hex_color = color_hex_map[label]
            rgb = (
                int(hex_color[1:3], 16),
                int(hex_color[3:5], 16),
                int(hex_color[5:7], 16),
            )

        mesh_obj = _triangles_to_trimesh(mesh_arrays, color_rgb=rgb)
        scene.add_geometry(mesh_obj, node_name=f"color_{label}")
        logger.info("SVG-3MF color '%s': %d triangles", label, len(mesh_obj.faces))

    if base_plate_thickness > 0:
        base_mesh_data = generate_box(
            xrange=(0, width * pixel_size),
            yrange=(0, height * pixel_size),
            zrange=(0, base_plate_thickness)
        )
        base_obj = _triangles_to_trimesh([base_mesh_data])
        scene.add_geometry(base_obj, node_name="base_plate")

    buf = BytesIO()
    scene.export(buf, file_type='3mf')
    result = buf.getvalue()

    logger.info(
        "Generated SVG 3MF file: %d objects, %d bytes",
        len(scene.geometry), len(result)
    )

    return result
