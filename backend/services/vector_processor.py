"""
Vector-based image processing for STL generation.

This module implements contour extraction and simplification
for generating vector-based 3D models instead of pixel-based ones.

Uses OpenCV for contour detection and Douglas-Peucker for simplification.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from services.raster_cleanup import merge_small_label_regions

logger = logging.getLogger(__name__)


@dataclass
class VectorProcessorConfig:
    """Configuration for vector processing pipeline."""
    epsilon: float = 2.0       # Douglas-Peucker simplification tolerance
    min_area: int = 100        # Minimum contour area in pixels
    num_colors: int = 8        # Number of colors to quantize to
    pixel_size: float = 1.0    # Physical pixel pitch in mm
    detail_size: Optional[float] = None  # Minimum physical feature size in mm


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    """Normalize a boolean/0-1 mask to uint8 0/255 for OpenCV."""
    if mask.dtype == bool:
        return mask.astype(np.uint8) * 255
    if mask.max() == 1:
        return mask.astype(np.uint8) * 255
    return mask.astype(np.uint8)


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
    mask = _normalize_mask(mask)

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


def find_contours_with_hierarchy(
    mask: np.ndarray,
) -> tuple[list[np.ndarray], Optional[np.ndarray]]:
    """Find contours and hierarchy, preserving holes."""
    mask = _normalize_mask(mask)
    contours, hierarchy = cv2.findContours(
        mask,
        cv2.RETR_CCOMP,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    result = []
    for contour in contours:
        if len(contour) >= 3:
            result.append(contour.reshape(-1, 2).astype(np.float32))
        else:
            result.append(np.zeros((0, 2), dtype=np.float32))

    if hierarchy is None:
        return result, None

    return result, hierarchy[0]


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


def simplify_contour_preserving_shape(
    contour: np.ndarray,
    epsilon: float,
    clockwise: bool,
) -> np.ndarray:
    """Simplify a contour but fall back to the original if it degenerates."""
    simplified = _ensure_orientation(simplify_contour(contour, epsilon), clockwise=clockwise)
    if len(simplified) >= 3:
        return simplified
    return _ensure_orientation(contour.copy(), clockwise=clockwise)


def _signed_area(contour: np.ndarray) -> float:
    """Return the signed area of a contour."""
    if len(contour) < 3:
        return 0.0
    points = contour.astype(np.float64)
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _ensure_orientation(contour: np.ndarray, clockwise: bool) -> np.ndarray:
    """Force contour winding for stable downstream handling."""
    if len(contour) < 3:
        return contour

    is_clockwise = _signed_area(contour) < 0
    if is_clockwise != clockwise:
        return contour[::-1].copy()
    return contour


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


def extract_regions_from_mask(
    mask: np.ndarray,
    epsilon: float,
    min_area: int,
) -> list[dict]:
    """
    Extract simplified vector regions from a mask.

    Each region contains one exterior ring and zero or more holes.
    Small exterior regions are filtered by ``min_area`` while holes are kept
    if they survive simplification, so the final geometry matches the source
    mask as closely as possible.
    """
    contours, hierarchy = find_contours_with_hierarchy(mask)
    if not contours or hierarchy is None:
        return []

    regions = []
    for idx, contour in enumerate(contours):
        if len(contour) < 3:
            continue

        parent_idx = int(hierarchy[idx][3])
        if parent_idx != -1:
            continue

        area = cv2.contourArea(contour.reshape(-1, 1, 2))
        if area < min_area:
            continue

        outer = simplify_contour_preserving_shape(contour, epsilon, clockwise=False)

        holes = []
        child_idx = int(hierarchy[idx][2])
        while child_idx != -1:
            child = contours[child_idx]
            if len(child) >= 3:
                simplified_hole = simplify_contour_preserving_shape(
                    child,
                    epsilon,
                    clockwise=True,
                )
                if len(simplified_hole) >= 3:
                    holes.append(simplified_hole)
            child_idx = int(hierarchy[child_idx][0])

        regions.append({
            'outer': contour_to_polygon(outer, pixel_size=1.0),
            'holes': [contour_to_polygon(hole, pixel_size=1.0) for hole in holes],
        })

    return regions


def normalize_regions(result: dict) -> list[dict]:
    """Return vector regions from either the new or legacy result shape."""
    if result.get('regions'):
        normalized = []
        for region in result['regions']:
            normalized.append({
                'outer': [
                    (float(point[0]), float(point[1]))
                    for point in region.get('outer', [])
                ],
                'holes': [
                    [(float(point[0]), float(point[1])) for point in hole]
                    for hole in region.get('holes', [])
                ],
            })
        return normalized

    return [
        {
            'outer': [(float(point[0]), float(point[1])) for point in polygon],
            'holes': [],
        }
        for polygon in result.get('polygons', [])
    ]


def render_region_mask(
    regions: list[dict],
    width: int,
    height: int,
) -> np.ndarray:
    """Rasterize vector regions back into a boolean mask."""
    mask = np.zeros((height, width), dtype=np.uint8)

    for region in regions:
        outer = region.get('outer', [])
        if len(outer) < 3:
            continue

        outer_pts = np.round(np.array(outer, dtype=np.float32)).astype(np.int32)
        cv2.fillPoly(mask, [outer_pts], 255)

        for hole in region.get('holes', []):
            if len(hole) < 3:
                continue
            hole_pts = np.round(np.array(hole, dtype=np.float32)).astype(np.int32)
            cv2.fillPoly(mask, [hole_pts], 0)

    return mask > 0


def count_region_points(regions: list[dict]) -> int:
    """Count points across outer rings and holes."""
    total = 0
    for region in regions:
        total += len(region.get('outer', []))
        total += sum(len(hole) for hole in region.get('holes', []))
    return total


def render_vector_results_image(
    image_dimensions: dict,
    vector_results: list[dict],
    fill_colors: Optional[list[tuple[int, int, int]]] = None,
    background_color: tuple[int, int, int] = (255, 255, 255),
    outline_color: Optional[tuple[int, int, int]] = None,
) -> np.ndarray:
    """Render vector results from their final geometry for preview parity."""
    width = int(image_dimensions['width'])
    height = int(image_dimensions['height'])
    image = np.full((height, width, 3), background_color, dtype=np.uint8)

    if not vector_results:
        return image

    for idx, result in enumerate(vector_results):
        regions = normalize_regions(result)
        region_mask = render_region_mask(regions, width=width, height=height)
        if not region_mask.any():
            continue
        fill_rgb = (
            fill_colors[idx]
            if fill_colors is not None
            else tuple(int(channel) for channel in result['color'])
        )
        fill_arr = np.array(fill_rgb, dtype=np.uint8)
        image[region_mask] = fill_arr

        if outline_color is not None:
            for region in regions:
                outer = region.get('outer', [])
                if len(outer) < 3:
                    continue

                outer_pts = np.round(np.array(outer, dtype=np.float32)).astype(np.int32)
                cv2.polylines(
                    image,
                    [outer_pts],
                    isClosed=True,
                    color=outline_color,
                    thickness=1,
                )
                for hole in region.get('holes', []):
                    if len(hole) < 3:
                        continue
                    hole_pts = np.round(np.array(hole, dtype=np.float32)).astype(np.int32)
                    cv2.polylines(
                        image,
                        [hole_pts],
                        isClosed=True,
                        color=outline_color,
                        thickness=1,
                    )

    return image


def quantize_colors(
    image: np.ndarray,
    num_colors: int
) -> tuple[np.ndarray, list[tuple[int, int, int]]]:
    """
    Reduce image to limited number of colors using k-means clustering.

    Uses the most frequent original color within each cluster as the
    representative color, instead of the cluster center. This preserves
    extreme colors (brightest/darkest) that would otherwise be lost to
    averaging.

    Args:
        image: RGB image array
        num_colors: Target number of colors

    Returns:
        Tuple of (quantized image, list of color tuples)
    """
    quantized, _, colors = quantize_colors_with_labels(image, num_colors)
    return quantized, colors


def quantize_colors_with_labels(
    image: np.ndarray,
    num_colors: int,
) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int]]]:
    """Reduce image colors and keep the per-pixel label grid."""
    pixels = image.reshape(-1, 3).astype(np.float32)
    pixels_uint8 = image.reshape(-1, 3)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    _, labels, _ = cv2.kmeans(
        pixels,
        num_colors,
        None,
        criteria,
        10,
        cv2.KMEANS_PP_CENTERS
    )

    labels_flat = labels.flatten()
    label_grid = labels_flat.reshape(image.shape[:2]).astype(np.int32)

    colors = []
    representative_colors = np.zeros((num_colors, 3), dtype=np.uint8)

    for label in range(num_colors):
        cluster_mask = labels_flat == label
        cluster_pixels = pixels_uint8[cluster_mask]

        if len(cluster_pixels) > 0:
            unique_colors, counts = np.unique(
                cluster_pixels, axis=0, return_counts=True
            )
            most_frequent_idx = np.argmax(counts)
            representative = unique_colors[most_frequent_idx]
            representative_colors[label] = representative
            colors.append(tuple(map(int, representative)))
        else:
            colors.append((0, 0, 0))

    quantized = representative_colors[labels_flat].reshape(image.shape)
    return quantized, label_grid, colors


def render_quantized_labels(
    label_grid: np.ndarray,
    colors: list[tuple[int, int, int]],
) -> np.ndarray:
    """Render an RGB image from a label grid and palette."""
    palette = np.array(colors, dtype=np.uint8)
    return palette[label_grid]


def process_image_vector_with_preview(
    image: np.ndarray,
    config: VectorProcessorConfig,
) -> tuple[list[dict], np.ndarray]:
    """Vectorize a quantized image and return the cleaned preview image."""
    logger.info(
        "Processing image %dx%d with vector mode (epsilon=%.1f, min_area=%d)",
        image.shape[1], image.shape[0], config.epsilon, config.min_area
    )

    _, label_grid, colors = quantize_colors_with_labels(image, config.num_colors)
    
    # First, remove thin features that would be unprintable
    from services.raster_cleanup import remove_thin_features
    filtered_labels = remove_thin_features(
        labels=label_grid,
        colors=colors,
        pixel_size=config.pixel_size,
        detail_size=config.detail_size,
    )
    
    # Then merge small isolated regions
    cleaned_labels = merge_small_label_regions(
        labels=filtered_labels,
        colors=colors,
        pixel_size=config.pixel_size,
        detail_size=config.detail_size,
    )
    quantized = render_quantized_labels(cleaned_labels, colors)

    results = []
    total_original_pixels = 0
    total_polygon_points = 0

    for label, color in enumerate(colors):
        mask = cleaned_labels == label
        pixel_count = int(mask.sum())

        if pixel_count == 0:
            continue

        total_original_pixels += pixel_count

        regions = extract_regions_from_mask(
            mask=mask.astype(np.uint8),
            epsilon=config.epsilon,
            min_area=config.min_area,
        )

        if regions:
            final_mask = render_region_mask(
                regions,
                width=image.shape[1],
                height=image.shape[0],
            )
            final_pixel_count = int(final_mask.sum())
            point_count = count_region_points(regions)
            total_polygon_points += point_count

            results.append({
                'color': color,
                'regions': regions,
                'polygons': [region['outer'] for region in regions],
                'pixel_count': final_pixel_count,
                'polygon_points': point_count
            })

    logger.info(
        "Vector processing complete: %d pixels -> %d polygon points (%.1f%% reduction)",
        total_original_pixels,
        total_polygon_points,
        (1 - total_polygon_points / max(total_original_pixels, 1)) * 100
    )

    return results, quantized


def process_image_vector(
    image: np.ndarray,
    config: VectorProcessorConfig
) -> list[dict]:
    """
    Process image using vector contour extraction.

    Full pipeline:
    1. Quantize colors
    2. Remove sub-threshold raster islands if detail_size requires it
    3. For each color, extract contours
    4. Simplify contours
    5. Filter small contours
    6. Convert to polygon format
    """
    results, _ = process_image_vector_with_preview(image, config)
    return results
