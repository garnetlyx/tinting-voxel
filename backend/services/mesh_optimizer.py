"""
Mesh optimization algorithms for STL file size reduction.

This module implements:
1. Greedy Meshing - Merges adjacent same-color pixels into larger rectangles
2. Internal Face Culling - Removes hidden faces between adjacent boxes
"""
import logging
from enum import Enum, auto

import numpy as np

logger = logging.getLogger(__name__)


class FaceDirection(Enum):
    """Enum representing the six faces of a 3D box."""
    BOTTOM = auto()  # -Z face
    TOP = auto()     # +Z face
    LEFT = auto()    # -X face
    RIGHT = auto()   # +X face
    FRONT = auto()   # -Y face
    BACK = auto()    # +Y face


def pixels_to_grid(
    pixels: list[dict[str, int]],
    width: int,
    height: int
) -> np.ndarray:
    """
    Convert a list of pixel positions to a 2D boolean grid.

    Args:
        pixels: List of pixel dicts with 'x' and 'y' keys
        width: Grid width
        height: Grid height

    Returns:
        2D numpy boolean array where True indicates a pixel is present
    """
    grid = np.zeros((height, width), dtype=bool)
    dropped = 0
    for pixel in pixels:
        x, y = pixel['x'], pixel['y']
        if 0 <= x < width and 0 <= y < height:
            grid[y, x] = True
        else:
            dropped += 1
    if dropped > 0:
        if dropped == len(pixels):
            raise ValueError(
                f"All {dropped} pixel(s) are outside image bounds "
                f"({width}x{height}). Check image dimensions."
            )
        logger.warning(
            "Dropped %d of %d pixels outside image bounds (%dx%d)",
            dropped, len(pixels), width, height
        )
    return grid


def find_max_rectangle(
    grid: np.ndarray,
    start_x: int,
    start_y: int
) -> tuple[int, int, int, int]:
    """
    Find the maximum rectangle starting from a given position.

    Uses a greedy approach: first expand width as far as possible,
    then expand height while maintaining full width.

    Args:
        grid: 2D boolean grid
        start_x: Starting x coordinate
        start_y: Starting y coordinate

    Returns:
        Tuple of (x, y, width, height) for the rectangle
    """
    if not grid[start_y, start_x]:
        return (start_x, start_y, 0, 0)

    height, width = grid.shape

    # Find maximum width at starting row
    max_width = 0
    for x in range(start_x, width):
        if grid[start_y, x]:
            max_width += 1
        else:
            break

    # Find maximum height that maintains this width
    max_height = 1
    for y in range(start_y + 1, height):
        # Check if entire row segment is set
        if np.all(grid[y, start_x:start_x + max_width]):
            max_height += 1
        else:
            break

    return (start_x, start_y, max_width, max_height)


def greedy_mesh_2d(grid: np.ndarray) -> list[tuple[int, int, int, int]]:
    """
    Apply greedy meshing algorithm to merge pixels into rectangles.

    Scans the grid left-to-right, top-to-bottom. For each unprocessed
    pixel, finds the maximum rectangle and marks it as processed.

    Args:
        grid: 2D boolean grid where True indicates a pixel is present

    Returns:
        List of rectangles as (x, y, width, height) tuples
    """
    if not grid.any():
        return []

    # Work on a copy to avoid modifying original
    remaining = grid.copy()
    rectangles = []

    height, width = grid.shape

    # Scan left-to-right, top-to-bottom
    for y in range(height):
        for x in range(width):
            if remaining[y, x]:
                # Find maximum rectangle starting here
                rect = find_max_rectangle(remaining, x, y)
                rx, ry, rw, rh = rect

                if rw > 0 and rh > 0:
                    rectangles.append(rect)
                    # Mark as processed
                    remaining[ry:ry + rh, rx:rx + rw] = False

    logger.debug(
        "Greedy meshing: %d pixels -> %d rectangles",
        grid.sum(),
        len(rectangles)
    )

    return rectangles


def generate_optimized_boxes(
    pixels: list[dict[str, int]],
    width: int,
    height: int,
    pixel_size: float,
    z_min: float,
    z_max: float
) -> list[tuple[tuple[float, float], tuple[float, float], tuple[float, float]]]:
    """
    Generate optimized box ranges using greedy meshing.

    Instead of one box per pixel, merges adjacent pixels into larger boxes.

    Args:
        pixels: List of pixel dicts with 'x' and 'y' keys
        width: Image width in pixels
        height: Image height in pixels
        pixel_size: Physical size of each pixel in mm
        z_min: Z start coordinate in mm
        z_max: Z end coordinate in mm

    Returns:
        List of (xrange, yrange, zrange) tuples for each optimized box
    """
    grid = pixels_to_grid(pixels, width, height)
    rectangles = greedy_mesh_2d(grid)

    boxes = []
    for x, y, w, h in rectangles:
        xrange = (x * pixel_size, (x + w) * pixel_size)
        yrange = (y * pixel_size, (y + h) * pixel_size)
        zrange = (z_min, z_max)
        boxes.append((xrange, yrange, zrange))

    logger.info(
        "Optimized %d pixels into %d boxes (%.1f%% reduction)",
        len(pixels),
        len(boxes),
        (1 - len(boxes) / max(len(pixels), 1)) * 100
    )

    return boxes


# =============================================================================
# Internal Face Culling Functions
# =============================================================================

def build_adjacency_map(
    rectangles: list[tuple[int, int, int, int]]
) -> dict[int, dict[FaceDirection, bool]]:
    """
    Build adjacency map for rectangles to detect shared edges.

    For each rectangle, determines which faces are adjacent to other rectangles.

    Args:
        rectangles: List of (x, y, width, height) tuples

    Returns:
        Dict mapping rectangle index to dict of FaceDirection -> has_neighbor
    """
    adj_map = {}

    for idx, _rect in enumerate(rectangles):
        adj_map[idx] = dict.fromkeys(FaceDirection, False)

    # Check all pairs for adjacency
    for i, rect1 in enumerate(rectangles):
        x1, y1, w1, h1 = rect1

        for j, rect2 in enumerate(rectangles):
            if i == j:
                continue

            x2, y2, w2, h2 = rect2

            # Check if rect2 is to the right of rect1 (touching at x1+w1 == x2)
            if x1 + w1 == x2:
                # Check y overlap
                if _ranges_overlap(y1, y1 + h1, y2, y2 + h2):
                    adj_map[i][FaceDirection.RIGHT] = True
                    adj_map[j][FaceDirection.LEFT] = True

            # Check if rect2 is above rect1 in y direction (touching at y1+h1 == y2)
            if y1 + h1 == y2:
                # Check x overlap
                if _ranges_overlap(x1, x1 + w1, x2, x2 + w2):
                    adj_map[i][FaceDirection.BACK] = True
                    adj_map[j][FaceDirection.FRONT] = True

    return adj_map


def _ranges_overlap(a_min: int, a_max: int, b_min: int, b_max: int) -> bool:
    """Check if two 1D ranges overlap (touching counts as overlap)."""
    return a_min < b_max and b_min < a_max


def get_visible_faces(
    neighbors: dict[FaceDirection, bool]
) -> dict[FaceDirection, bool]:
    """
    Determine which faces are visible based on neighbor presence.

    A face is visible if there is no neighbor in that direction.

    Args:
        neighbors: Dict of FaceDirection -> has_neighbor

    Returns:
        Dict of FaceDirection -> is_visible
    """
    return {d: not has_neighbor for d, has_neighbor in neighbors.items()}


def generate_box_with_culling(
    xrange: tuple[float, float],
    yrange: tuple[float, float],
    zrange: tuple[float, float],
    visible_faces: dict[FaceDirection, bool]
) -> np.ndarray:
    """
    Generate a 3D box mesh with face culling.

    Only generates triangles for visible faces, reducing polygon count
    for adjacent boxes.

    Args:
        xrange: (x_min, x_max) in mm
        yrange: (y_min, y_max) in mm
        zrange: (z_min, z_max) in mm
        visible_faces: Dict indicating which faces to generate

    Returns:
        Numpy array of mesh vertices (N triangles x 3 vertices x 3 coords)
        where N depends on number of visible faces
    """
    x1, x2 = xrange
    y1, y2 = yrange
    z1, z2 = zrange

    # 8 vertices of the box
    vertices = np.array([
        [x1, y1, z1],  # 0: front-left-bottom
        [x2, y1, z1],  # 1: front-right-bottom
        [x2, y2, z1],  # 2: back-right-bottom
        [x1, y2, z1],  # 3: back-left-bottom
        [x1, y1, z2],  # 4: front-left-top
        [x2, y1, z2],  # 5: front-right-top
        [x2, y2, z2],  # 6: back-right-top
        [x1, y2, z2]   # 7: back-left-top
    ])

    # Face definitions: (direction, triangle1_indices, triangle2_indices)
    face_triangles = {
        FaceDirection.BOTTOM: ([0, 3, 1], [1, 3, 2]),  # -Z
        FaceDirection.TOP: ([4, 5, 6], [4, 6, 7]),     # +Z
        FaceDirection.LEFT: ([0, 4, 7], [0, 7, 3]),    # -X
        FaceDirection.RIGHT: ([5, 1, 2], [5, 2, 6]),   # +X
        FaceDirection.FRONT: ([0, 1, 5], [0, 5, 4]),   # -Y
        FaceDirection.BACK: ([2, 3, 6], [3, 7, 6]),    # +Y
    }

    triangles = []
    for direction, (tri1_idx, tri2_idx) in face_triangles.items():
        if visible_faces.get(direction, True):
            triangles.append(vertices[tri1_idx])
            triangles.append(vertices[tri2_idx])

    if not triangles:
        return np.zeros((0, 3, 3))

    return np.array(triangles)
