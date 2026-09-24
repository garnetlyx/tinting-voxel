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
    if not pixels:
        return grid
    xs = np.fromiter((pixel['x'] for pixel in pixels), dtype=np.int64, count=len(pixels))
    ys = np.fromiter((pixel['y'] for pixel in pixels), dtype=np.int64, count=len(pixels))
    inside = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    dropped = len(pixels) - int(inside.sum())
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
    grid[ys[inside], xs[inside]] = True
    return grid


class MeshTooComplexError(ValueError):
    """Raised when greedy meshing would produce more rectangles than the
    memory budget (settings.stl_max_boxes) allows."""


def greedy_mesh_2d(
    grid: np.ndarray,
    max_rectangles: int | None = None,
) -> list[tuple[int, int, int, int]]:
    """
    Cover the set cells of a grid with disjoint rectangles.

    Each row splits into horizontal runs, and identical runs on consecutive
    rows merge into one rectangle. Fully vectorized over the grid's bounding
    box; rectangles are returned in scan order (top to bottom, left to right).

    Args:
        grid: 2D boolean grid where True indicates a pixel is present
        max_rectangles: abort with MeshTooComplexError once more rectangles
            than this would be produced, so pathological (noise-like) inputs
            fail fast instead of exhausting memory

    Returns:
        List of rectangles as (x, y, width, height) tuples
    """
    rows = np.flatnonzero(grid.any(axis=1))
    if len(rows) == 0:
        return []
    cols = np.flatnonzero(grid.any(axis=0))
    y_off, x_off = int(rows[0]), int(cols[0])
    sub = grid[y_off:int(rows[-1]) + 1, x_off:int(cols[-1]) + 1]

    edges = np.diff(np.pad(sub.astype(np.int8), ((0, 0), (1, 1))), axis=1)
    run_y, run_x0 = np.nonzero(edges == 1)
    _, run_x1 = np.nonzero(edges == -1)  # row-major: the k-th end closes the k-th start

    order = np.lexsort((run_y, run_x1, run_x0))
    run_y, run_x0, run_x1 = run_y[order], run_x0[order], run_x1[order]
    opens = np.ones(len(run_y), dtype=bool)
    opens[1:] = (
        (run_x0[1:] != run_x0[:-1]) | (run_x1[1:] != run_x1[:-1]) | (run_y[1:] != run_y[:-1] + 1)
    )
    first = np.flatnonzero(opens)
    last = np.append(first[1:], len(run_y)) - 1
    if max_rectangles is not None and len(first) > max_rectangles:
        raise MeshTooComplexError(
            f"Greedy meshing exceeded {max_rectangles:,} rectangles; "
            f"the image has too much fine detail to mesh within the "
            f"memory budget. Reduce image size or increase color merge."
        )

    rect_x, rect_y = run_x0[first] + x_off, run_y[first] + y_off
    rect_w, rect_h = run_x1[first] - run_x0[first], run_y[last] - run_y[first] + 1
    scan = np.lexsort((rect_x, rect_y))
    rectangles = list(zip(
        rect_x[scan].tolist(), rect_y[scan].tolist(), rect_w[scan].tolist(), rect_h[scan].tolist(),
    ))
    logger.debug("Greedy meshing: %d pixels -> %d rectangles", int(sub.sum()), len(rectangles))
    return rectangles


BoxRange = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def boxes_from_rectangles(
    rectangles: list[tuple[int, int, int, int]],
    pixel_size: float,
    z_min: float,
    z_max: float,
) -> list[BoxRange]:
    """Extrude grid rectangles (x, y, width, height) into box ranges in mm."""
    return [
        ((x * pixel_size, (x + w) * pixel_size), (y * pixel_size, (y + h) * pixel_size), (z_min, z_max))
        for x, y, w, h in rectangles
    ]


def generate_optimized_boxes(
    pixels: list[dict[str, int]],
    width: int,
    height: int,
    pixel_size: float,
    z_min: float,
    z_max: float,
    max_rectangles: int | None = None,
) -> list[BoxRange]:
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
    return generate_optimized_boxes_from_grid(grid, pixel_size, z_min, z_max, max_rectangles)


def generate_optimized_boxes_from_grid(
    grid: np.ndarray,
    pixel_size: float,
    z_min: float,
    z_max: float,
    max_rectangles: int | None = None,
) -> list[BoxRange]:
    """
    Generate optimized boxes directly from a boolean grid.

    This avoids materializing large pixel lists when geometry is already
    available as a rasterized occupancy mask.
    """
    rectangles = greedy_mesh_2d(grid, max_rectangles=max_rectangles)
    return boxes_from_rectangles(rectangles, pixel_size, z_min, z_max)


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
