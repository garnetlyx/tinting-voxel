"""
SVG mode STL generation service with polygon extrusion.

Converts vector contours to 3D meshes using triangulation and extrusion.
Uses Beer-Lambert color mapping (shared with pixel mode).
"""
import itertools
import logging
import zipfile
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import numpy as np

from core.blend_color import Color, Colors
from config.settings import settings
from services.mesh_optimizer import generate_optimized_boxes_from_grid
from services import stl_generator
from services.print_stack import (
    build_print_stack,
    normalize_white_backing_layers,
    resolve_white_backing_label,
)
from services.stl_generator import (
    generate_box,
    generate_boxes_batch,
    get_filename_prefix,
    merge_stl_meshes,
    _log_blend_code_distribution,
    _log_input_color_brightness,
)
from services.vector_processor import normalize_regions, render_region_mask

logger = logging.getLogger(__name__)


@dataclass
class SVGSTLConfig:
    """Configuration for SVG STL generation."""
    layer_height: float = 0.08
    pixel_size: float = 0.08
    layer_count: int = 4


def triangulate_polygon(polygon: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    """
    Triangulate a 2D polygon using ear clipping algorithm.

    Args:
        polygon: List of (x, y) coordinate tuples forming a closed polygon

    Returns:
        List of triangle indices (i, j, k) referencing the polygon vertices

    Raises:
        ValueError: If polygon has more than 1000 vertices (DoS protection)
    """
    if len(polygon) < 3:
        return []

    # P0 Security: Limit maximum vertices to prevent DoS attacks (QA code review)
    MAX_VERTICES = 1000
    if len(polygon) > MAX_VERTICES:
        raise ValueError(
            f"Polygon has {len(polygon)} vertices, exceeding maximum of {MAX_VERTICES}. "
            f"Complex polygons may cause performance issues."
        )

    # Detect winding order using signed area
    # Positive = counter-clockwise, Negative = clockwise
    area = 0.0
    n = len(polygon)
    for i in range(n):
        j = (i + 1) % n
        area += (polygon[j][0] - polygon[i][0]) * (polygon[j][1] + polygon[i][1])

    # Reverse polygon if clockwise (negative area)
    if area < 0:
        polygon = list(reversed(polygon))

    # Work with a copy of indices
    indices = list(range(len(polygon)))
    triangles = []

    def is_convex(a: int, b: int, c: int) -> bool:
        """Check if angle ABC is convex (counter-clockwise)."""
        ax, ay = polygon[a]
        bx, by = polygon[b]
        cx, cy = polygon[c]
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) > 0

    def point_in_triangle(p: int, a: int, b: int, c: int) -> bool:
        """Check if point p is inside triangle ABC."""
        px, py = polygon[p]
        ax, ay = polygon[a]
        bx, by = polygon[b]
        cx, cy = polygon[c]

        def sign(p1x, p1y, p2x, p2y, p3x, p3y):
            return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)

        d1 = sign(px, py, ax, ay, bx, by)
        d2 = sign(px, py, bx, by, cx, cy)
        d3 = sign(px, py, cx, cy, ax, ay)

        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)

        return not (has_neg and has_pos)

    def is_ear(i: int) -> bool:
        """Check if vertex at index i is an ear."""
        n = len(indices)
        if n < 3:
            return False

        prev_idx = (i - 1) % n
        next_idx = (i + 1) % n

        a = indices[prev_idx]
        b = indices[i]
        c = indices[next_idx]

        # Must be convex
        if not is_convex(a, b, c):
            return False

        # No other vertex should be inside the triangle
        for j in range(n):
            if j in (prev_idx, i, next_idx):
                continue
            if point_in_triangle(indices[j], a, b, c):
                return False

        return True

    # Ear clipping loop
    max_iterations = len(polygon) * 2
    iteration = 0

    while len(indices) > 3 and iteration < max_iterations:
        iteration += 1
        ear_found = False

        for i in range(len(indices)):
            if is_ear(i):
                n = len(indices)
                prev_idx = (i - 1) % n
                next_idx = (i + 1) % n

                a = indices[prev_idx]
                b = indices[i]
                c = indices[next_idx]

                triangles.append((a, b, c))
                indices.pop(i)
                ear_found = True
                break

        if not ear_found:
            # Fallback: use fan triangulation from first vertex for remaining vertices
            # This handles complex polygons where ear clipping gets stuck
            remaining = indices
            for i in range(1, len(remaining) - 1):
                triangles.append((remaining[0], remaining[i], remaining[i + 1]))
            return triangles

    # Handle remaining triangle
    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))

    return triangles


def _fill_region_gaps(
    region_grids: list[np.ndarray],
    width: int,
    height: int,
) -> list[np.ndarray]:
    """
    Fill unassigned pixels (gaps between vector regions) using Voronoi
    nearest-neighbour assignment.

    When contours are simplified with Douglas-Peucker and rasterized back,
    adjacent polygons can leave 1-pixel gaps at shared boundaries. These gaps
    produce holes in the STL mesh. This function assigns each gap pixel to
    the nearest color region so the mesh is gap-free.

    Args:
        region_grids: Per-color boolean masks from render_region_mask.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Updated list of boolean masks with gaps filled.
    """
    if not region_grids:
        return region_grids

    # Build combined assigned mask
    combined = np.zeros((height, width), dtype=bool)
    for grid in region_grids:
        combined |= grid

    gap_mask = ~combined
    gap_count = int(gap_mask.sum())
    if gap_count == 0:
        return region_grids

    logger.info("SVG-STL: filling %d gap pixels via Voronoi nearest-neighbour", gap_count)

    # Build a label image: 0 = unassigned, 1..N = color index+1
    label_img = np.zeros((height, width), dtype=np.int32)
    for idx, grid in enumerate(region_grids):
        label_img[grid] = idx + 1  # 1-based so 0 stays "unassigned"

    # Use scipy distance transform to find, for each gap pixel, the coordinates
    # of the nearest assigned pixel, then look up its color label.
    from scipy.ndimage import distance_transform_edt
    _, nearest_indices = distance_transform_edt(
        ~combined,          # True = pixels to fill (gaps)
        return_indices=True,
    )
    # nearest_indices shape: (2, H, W) — [row_indices, col_indices]
    nearest_rows = nearest_indices[0]
    nearest_cols = nearest_indices[1]
    nearest_color = label_img[nearest_rows, nearest_cols]

    # Assign gap pixels to their nearest color
    result_grids = [grid.copy() for grid in region_grids]
    for idx in range(len(region_grids)):
        fill_mask = gap_mask & (nearest_color == idx + 1)
        if fill_mask.any():
            result_grids[idx] |= fill_mask

    return result_grids


def generate_polygon_mesh(
    polygon: list[tuple[float, float]],
    z_min: float,
    z_max: float,
    pixel_size: float
) -> np.ndarray:
    """
    Extrude a 2D polygon to create a 3D mesh.

    Creates bottom face, top face, and side faces.

    Args:
        polygon: List of (x, y) coordinate tuples
        z_min: Bottom z coordinate
        z_max: Top z coordinate
        pixel_size: Scale factor for coordinates

    Returns:
        Numpy array of triangles (Nx3x3)
    """
    if len(polygon) < 3:
        return np.array([]).reshape(0, 3, 3)

    # Scale polygon coordinates
    scaled_polygon = [(x * pixel_size, y * pixel_size) for x, y in polygon]
    n = len(scaled_polygon)

    triangles = []

    # Triangulate the polygon
    triangle_indices = triangulate_polygon(scaled_polygon)

    # Bottom face (z = z_min)
    for i, j, k in triangle_indices:
        v1 = [scaled_polygon[i][0], scaled_polygon[i][1], z_min]
        v2 = [scaled_polygon[j][0], scaled_polygon[j][1], z_min]
        v3 = [scaled_polygon[k][0], scaled_polygon[k][1], z_min]
        # Reverse winding for bottom face (normal points down)
        triangles.append([v1, v3, v2])

    # Top face (z = z_max)
    for i, j, k in triangle_indices:
        v1 = [scaled_polygon[i][0], scaled_polygon[i][1], z_max]
        v2 = [scaled_polygon[j][0], scaled_polygon[j][1], z_max]
        v3 = [scaled_polygon[k][0], scaled_polygon[k][1], z_max]
        triangles.append([v1, v2, v3])

    # Side faces (extrude edges)
    for i in range(n):
        j = (i + 1) % n

        x1, y1 = scaled_polygon[i]
        x2, y2 = scaled_polygon[j]

        # Two triangles per edge
        # Triangle 1: bottom-left, bottom-right, top-right
        v1 = [x1, y1, z_min]
        v2 = [x2, y2, z_min]
        v3 = [x2, y2, z_max]
        triangles.append([v1, v2, v3])

        # Triangle 2: bottom-left, top-right, top-left
        v1 = [x1, y1, z_min]
        v2 = [x2, y2, z_max]
        v3 = [x1, y1, z_max]
        triangles.append([v1, v2, v3])

    if not triangles:
        return np.array([]).reshape(0, 3, 3)

    return np.array(triangles, dtype=np.float32)


def generate_svg_stl_zip(
    vector_results: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    colors: Optional[Colors] = None,
    white_backing_layers: int = 1,
) -> bytes:
    """
    Generate ZIP file containing STL files from vector contours.

    Uses Beer-Lambert color mapping (same as pixel mode).

    Args:
        vector_results: List of dicts with 'color' and 'polygons' keys
            - color: RGB tuple (r, g, b)
            - polygons: List of polygon coordinate lists
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Total number of layers
        image_dimensions: Dict with 'width' and 'height' keys
        colors: Optional Colors instance. If None, uses current global colors.

    Returns:
        ZIP file binary content
    """
    # Use provided colors or fall back to global state
    active_colors = colors if colors is not None else stl_generator._current_colors
    if active_colors is None:
        raise RuntimeError("No colors provided and no global colors initialized.")

    # Compute reference matrices locally (thread-safe)
    ref_code_matrix, ref_rgb_matrix = stl_generator.compute_reference_matrices(
        layer_count, layer_height, active_colors
    )

    # Initialize mesh map for each primary color dynamically
    code_mesh_map = {label: [] for label in active_colors.get_labels()}

    # Extract colors from vector results
    input_colors = [result['color'] for result in vector_results]

    # Map to blend codes using Beer-Lambert model (with order refinement
    # for composition-pruned translucent sets)
    from services.image_processor import _map_and_refine
    result_codes, result_rgbs = _map_and_refine(
        input_colors, ref_code_matrix, ref_rgb_matrix,
        active_colors, layer_count, layer_height,
    )

    _log_input_color_brightness(input_colors, "SVG-STL")
    _log_blend_code_distribution(result_codes, active_colors.get_labels(), "SVG-STL")

    width = image_dimensions['width']
    height = image_dimensions['height']
    total_regions = 0
    total_boxes = 0

    z_offset = 0.0

    n_white = normalize_white_backing_layers(white_backing_layers)
    w_label = resolve_white_backing_label(active_colors, n_white)
    if n_white > 0:
        logger.info("SVG-STL: white backing label='%s', n_white=%d", w_label, n_white)

    # Rasterize all region masks upfront, then fill inter-region gaps via
    # Voronoi nearest-neighbour so no pixel is left unassigned (which would
    # produce holes in the mesh).
    region_grids = []
    for result in vector_results:
        regions = normalize_regions(result)
        region_grids.append(render_region_mask(regions, width=width, height=height))

    region_grids = _fill_region_gaps(region_grids, width, height)

    # Process each color group
    for idx, result in enumerate(vector_results):
        region_grid = region_grids[idx]
        if not region_grid.any():
            continue
        total_regions += len(normalize_regions(result))
        blend_code = result_codes[idx]

        # Generate mesh for each layer
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
                max_rectangles=max(0, settings.stl_max_boxes - total_boxes),
            )
            if boxes:
                total_boxes += len(boxes)
                code_mesh_map[code_char].append(generate_boxes_batch(boxes))

    logger.info(
        "SVG STL generation: %d regions -> %d boxes",
        total_regions, total_boxes
    )

    # Add white backing above optical layers (reflector behind colors)
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
        logger.info("SVG-STL: added 1 merged white backing block thickness=%.2f mm at z=%.2f-%.2f mm",
                     n_white * layer_height, optical_top, optical_top + n_white * layer_height)

    # Merge meshes by primary color and create STL files
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
            merged_stl = merge_stl_meshes(meshes)
            filename = f"{prefix}_{width}x{height}x{physical_height:.2f}_{code}.stl"
            stl_files[filename] = merged_stl

    # Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, stl_content in stl_files.items():
            zip_file.writestr(filename, stl_content)

    return zip_buffer.getvalue()
