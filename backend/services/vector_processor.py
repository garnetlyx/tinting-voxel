"""
Vector-based image processing for STL generation.

This module implements contour extraction and simplification
for generating vector-based 3D models instead of pixel-based ones.

Uses OpenCV for contour detection and Douglas-Peucker for simplification.
"""
import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorProcessorConfig:
    """Configuration for vector processing pipeline."""
    epsilon: float = 2.0       # Douglas-Peucker simplification tolerance
    min_area: int = 100        # Minimum contour area in pixels
    num_colors: int = 8        # Number of colors to quantize to


def extract_color_mask(
    image: np.ndarray,
    color: tuple[int, int, int],
    tolerance: int = 0
) -> np.ndarray:
    """
    Create a binary mask for pixels matching the specified color.

    Args:
        image: RGB image array (H, W, 3)
        color: Target RGB color tuple
        tolerance: Color matching tolerance (0 = exact match)

    Returns:
        Boolean mask array (H, W) where True indicates color match
    """
    if tolerance == 0:
        # Exact match
        mask = np.all(image == color, axis=2)
    else:
        # Match with tolerance
        lower = np.array([max(0, c - tolerance) for c in color], dtype=np.uint8)
        upper = np.array([min(255, c + tolerance) for c in color], dtype=np.uint8)
        mask = cv2.inRange(image, lower, upper) > 0

    return mask


def find_contours(mask: np.ndarray) -> list[np.ndarray]:
    """
    Find contours in a binary mask.

    Args:
        mask: Binary mask (uint8 or bool), non-zero values are foreground

    Returns:
        List of contour arrays, each is (N, 2) array of points
    """
    # Ensure uint8 format for OpenCV
    if mask.dtype == bool:
        mask = mask.astype(np.uint8) * 255
    elif mask.max() == 1:
        mask = mask * 255

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # Convert to simpler format (N, 2) instead of (N, 1, 2)
    result = []
    for contour in contours:
        if len(contour) >= 3:  # Need at least 3 points for a polygon
            result.append(contour.reshape(-1, 2).astype(np.float32))

    return result


def simplify_contour(
    contour: np.ndarray,
    epsilon: float
) -> np.ndarray:
    """
    Simplify contour using Douglas-Peucker algorithm.

    Args:
        contour: Contour array (N, 2)
        epsilon: Simplification tolerance (higher = simpler)

    Returns:
        Simplified contour array
    """
    # Ensure correct shape for OpenCV
    if contour.ndim == 2:
        contour = contour.reshape(-1, 1, 2)

    simplified = cv2.approxPolyDP(
        contour.astype(np.float32),
        epsilon,
        closed=True
    )

    return simplified.reshape(-1, 2)


def filter_small_contours(
    contours: list[np.ndarray],
    min_area: int
) -> list[np.ndarray]:
    """
    Filter out contours smaller than minimum area.

    Args:
        contours: List of contour arrays
        min_area: Minimum area threshold in pixels

    Returns:
        Filtered list of contours
    """
    result = []
    for contour in contours:
        # Reshape for cv2.contourArea if needed
        if contour.ndim == 2:
            area_contour = contour.reshape(-1, 1, 2)
        else:
            area_contour = contour

        area = cv2.contourArea(area_contour)
        if area >= min_area:
            result.append(contour)

    return result


def contour_to_polygon(
    contour: np.ndarray,
    pixel_size: float = 1.0
) -> list[tuple[float, float]]:
    """
    Convert contour array to polygon coordinate list.

    Args:
        contour: Contour array (N, 2)
        pixel_size: Physical size of each pixel for scaling

    Returns:
        List of (x, y) coordinate tuples
    """
    return [
        (float(point[0] * pixel_size), float(point[1] * pixel_size))
        for point in contour
    ]


def quantize_colors(
    image: np.ndarray,
    num_colors: int
) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """
    Reduce image to limited number of colors using k-means.

    Args:
        image: RGB image array
        num_colors: Target number of colors

    Returns:
        Tuple of (quantized image, list of color tuples)
    """
    # Reshape to list of pixels
    pixels = image.reshape(-1, 3).astype(np.float32)

    # K-means clustering
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, centers = cv2.kmeans(
        pixels,
        num_colors,
        None,
        criteria,
        10,
        cv2.KMEANS_PP_CENTERS
    )

    # Convert centers to uint8
    centers = np.uint8(centers)

    # Reconstruct image
    quantized = centers[labels.flatten()].reshape(image.shape)

    # Get unique colors
    colors = [tuple(map(int, c)) for c in centers]

    return quantized, colors


def process_image_vector(
    image: np.ndarray,
    config: VectorProcessorConfig
) -> list[dict]:
    """
    Process image using vector contour extraction.

    Full pipeline:
    1. Quantize colors
    2. For each color, extract contours
    3. Simplify contours
    4. Filter small contours
    5. Convert to polygon format

    Args:
        image: RGB image array (H, W, 3)
        config: Processing configuration

    Returns:
        List of dicts with 'color' and 'polygons' keys
    """
    logger.info(
        "Processing image %dx%d with vector mode (epsilon=%.1f, min_area=%d)",
        image.shape[1], image.shape[0], config.epsilon, config.min_area
    )

    # Step 1: Quantize colors
    quantized, colors = quantize_colors(image, config.num_colors)

    results = []
    total_original_pixels = 0
    total_polygon_points = 0

    # Step 2-5: Process each color
    for color in colors:
        # Extract mask for this color
        mask = extract_color_mask(quantized, color)
        pixel_count = mask.sum()

        if pixel_count == 0:
            continue

        total_original_pixels += pixel_count

        # Find contours
        contours = find_contours(mask.astype(np.uint8))

        # Simplify and filter
        simplified_contours = []
        for contour in contours:
            simplified = simplify_contour(contour, config.epsilon)
            simplified_contours.append(simplified)

        filtered = filter_small_contours(simplified_contours, config.min_area)

        # Convert to polygons
        polygons = [contour_to_polygon(c, pixel_size=1.0) for c in filtered]

        if polygons:
            point_count = sum(len(p) for p in polygons)
            total_polygon_points += point_count

            results.append({
                'color': color,
                'polygons': polygons,
                'pixel_count': int(pixel_count),
                'polygon_points': point_count
            })

    logger.info(
        "Vector processing complete: %d pixels -> %d polygon points (%.1f%% reduction)",
        total_original_pixels,
        total_polygon_points,
        (1 - total_polygon_points / max(total_original_pixels, 1)) * 100
    )

    return results
