"""
SVG mode STL generation service with polygon extrusion.

Converts vector contours to 3D meshes using triangulation and extrusion.
Uses Beer-Lambert color mapping (shared with pixel mode).
"""
import logging
import zipfile
from dataclasses import dataclass
from io import BytesIO

import numpy as np

from core.blend_color import Color
from services import stl_generator
from services.stl_generator import merge_stl_meshes

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
    """
    if len(polygon) < 3:
        return []

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
            # Fallback: use fan triangulation from first vertex
            break

    # Handle remaining triangle
    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))

    return triangles


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
    image_dimensions: dict
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

    Returns:
        ZIP file binary content
    """
    if stl_generator._reference_code_matrix is None:
        raise RuntimeError("Color mapping not initialized. Call initialize_color_mapping() first.")

    # Initialize mesh map for each primary color
    code_mesh_map = {
        'C': [],
        'M': [],
        'Y': [],
        'W': []
    }

    # Extract colors from vector results
    input_colors = [result['color'] for result in vector_results]

    # Map to blend codes using Beer-Lambert model
    result_codes, result_rgbs = Color.map_to_nearest_color(
        input_colors,
        stl_generator._reference_code_matrix,
        stl_generator._reference_rgb_matrix
    )

    width = image_dimensions['width']
    height = image_dimensions['height']
    total_polygons = 0
    total_triangles = 0

    # Process each color group
    for idx, result in enumerate(vector_results):
        polygons = result['polygons']
        blend_code = result_codes[idx]

        # Generate mesh for each layer
        for z_idx, code_char in enumerate(blend_code):
            z_min = z_idx * layer_height
            z_max = (z_idx + 1) * layer_height

            # Extrude each polygon
            for polygon in polygons:
                if len(polygon) < 3:
                    continue

                total_polygons += 1

                mesh = generate_polygon_mesh(
                    polygon=polygon,
                    z_min=z_min,
                    z_max=z_max,
                    pixel_size=pixel_size
                )

                if len(mesh) > 0:
                    total_triangles += len(mesh)
                    code_mesh_map[code_char].append(mesh)

    logger.info(
        "SVG STL generation: %d polygons -> %d triangles",
        total_polygons, total_triangles
    )

    # Merge meshes by primary color and create STL files
    stl_files = {}
    physical_height = layer_count * layer_height

    for code, meshes in code_mesh_map.items():
        if len(meshes) > 0:
            merged_stl = merge_stl_meshes(meshes)
            filename = f"CMYW_{width}x{height}x{physical_height:.2f}_{code}.stl"
            stl_files[filename] = merged_stl

    # Create ZIP archive
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, stl_content in stl_files.items():
            zip_file.writestr(filename, stl_content)

    return zip_buffer.getvalue()
