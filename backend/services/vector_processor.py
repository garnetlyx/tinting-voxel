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

from core.white_point import adapt_to_image_white
from services.raster_cleanup import regularize_printable_regions

logger = logging.getLogger(__name__)


@dataclass
class VectorProcessorConfig:
    """Configuration for vector processing pipeline."""
    epsilon: float = 2.0       # Douglas-Peucker simplification tolerance
    min_area: int = 100        # Minimum contour area in pixels (converted from mm² by route handler)
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
    """Return vector regions in the sole supported geometry representation."""
    return [
        {
            'outer': [
                (float(point[0]), float(point[1]))
                for point in region['outer']
            ],
            'holes': [
                [(float(point[0]), float(point[1])) for point in hole]
                for hole in region['holes']
            ],
        }
        for region in result['regions']
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


def finalize_vector_partition(
    vector_results: list[dict],
    image_dimensions: dict,
    pixel_size: float,
    detail_size: Optional[float],
) -> np.ndarray:
    """Return the printable, gap-free material assignment for SVG output.

    Simplified contours can overlap or leave pixels unassigned. Resolve overlaps
    in result order, assign every gap to its nearest surviving region, then
    apply the same physical feature cleanup as pixel mode. Preview and both
    mesh formats must consume this exact assignment.
    """
    width = int(image_dimensions['width'])
    height = int(image_dimensions['height'])
    if width <= 0 or height <= 0:
        raise ValueError('Image dimensions must be positive')
    if not vector_results:
        raise ValueError('No vector regions to print')

    labels = np.full((height, width), -1, dtype=np.int32)
    for idx, result in enumerate(vector_results):
        mask = render_region_mask(normalize_regions(result), width, height)
        labels[mask] = idx

    assigned = labels >= 0
    if not assigned.any():
        raise ValueError('Vector regions have no printable area')
    if not assigned.all():
        from scipy.ndimage import distance_transform_edt

        nearest = distance_transform_edt(
            ~assigned, return_distances=False, return_indices=True,
        )
        labels[~assigned] = labels[nearest[0][~assigned], nearest[1][~assigned]]

    if detail_size is not None and pixel_size < detail_size:
        colors = [tuple(int(channel) for channel in item['color']) for item in vector_results]
        labels = regularize_printable_regions(labels, colors, pixel_size, detail_size)

    return labels


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
    """Reduce image colors and keep the per-pixel label grid.

    Clustering uses a hue-priority feature space so that colors with the same
    hue angle cluster together regardless of lightness or chroma magnitude.

    Feature vector per pixel (4D):
        [L * W_L,  C * W_C,  cos(h) * W_H,  sin(h) * W_H]

    where L = CIELAB lightness, C = chroma = sqrt(a²+b²), h = arctan2(b, a).
    Hue terms are zeroed for neutral pixels (C < 8) AND for very dark pixels
    (L < 20), so near-black border pixels with JPEG color noise cluster
    together as a single "black" rather than splitting across hue clusters.

    Why unit hue direction instead of C·cos(h) / C·sin(h):
    - A dark muted blue (low C) and a bright saturated blue (high C) share
      the same hue angle → same (cos h, sin h) → cluster together.
    - With C·cos(h), the chroma magnitude difference dominates and splits them.
    - W_H = 60 makes a 25° hue difference ≈ 26 units (dominant signal).
    - W_C = 0.5 makes full chroma range ≈ 64 units (secondary).
    - W_L = 0.2 makes full lightness range ≈ 20 units (tertiary).
    """
    pixels_uint8 = image.reshape(-1, 3)

    # Convert to CIELAB
    # cv2 COLOR_RGB2Lab encodes: L in [0,255] (maps to [0,100]),
    # a and b in [0,255] (maps to [-128,127] via offset 128).
    pixels_lab_raw = cv2.cvtColor(
        pixels_uint8.reshape(1, -1, 3), cv2.COLOR_RGB2Lab
    ).reshape(-1, 3).astype(np.float32)

    L = pixels_lab_raw[:, 0] * (100.0 / 255.0)   # 0–100
    a = pixels_lab_raw[:, 1] - 128.0              # -128–127
    b = pixels_lab_raw[:, 2] - 128.0              # -128–127
    C = np.sqrt(a * a + b * b)    # chroma
    h = np.arctan2(b, a)          # hue angle in radians

    # Hue-priority feature space: [L, C, cos(h), sin(h)]
    #
    # Using unit hue direction (cos h, sin h) rather than chroma-scaled
    # (C·cos h, C·sin h) ensures that two colors at the same hue angle
    # cluster together regardless of their chroma magnitude.  A dark muted
    # blue (low C) and a bright saturated blue (high C) share the same hue
    # direction and therefore land in the same cluster.
    #
    # Hue terms are suppressed (zeroed) when EITHER:
    #   - C < NEUTRAL_C: truly neutral/achromatic pixel (hue is undefined)
    #   - L < DARK_L:    very dark pixel whose slight color cast is JPEG
    #                    compression noise, not a meaningful hue difference.
    #                    Without this, near-black border pixels (e.g. RGB
    #                    [28,6,8], C≈10) get split across hue clusters instead
    #                    of merging into a single "black" cluster.
    #
    # Weight rationale:
    #   W_H = 60  → hue direction dominates; a 25° hue difference ≈ 26 units
    #   W_C = 0.5 → chroma is secondary; full chroma range (0–128) ≈ 64 units
    #   W_L = 0.2 → lightness is tertiary; full L range (0–100) ≈ 20 units
    NEUTRAL_C = 8.0
    DARK_L = 20.0   # suppress hue for very dark pixels (JPEG noise)
    W_L = 0.2
    W_C = 0.5
    W_H = 60.0

    hue_active = (C >= NEUTRAL_C) & (L >= DARK_L)
    cos_h = np.where(hue_active, np.cos(h), 0.0).astype(np.float32)
    sin_h = np.where(hue_active, np.sin(h), 0.0).astype(np.float32)

    pixels_lch_weighted = np.stack([
        L * W_L,
        C * W_C,
        cos_h * W_H,
        sin_h * W_H,
    ], axis=1).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
    # k-means++ draws from OpenCV's per-thread RNG, whose state carries over
    # between calls; reseed it so an image always clusters the same way.
    cv2.setRNGSeed(0)
    _, labels, _ = cv2.kmeans(
        pixels_lch_weighted,
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
    
    # Quantized colors must meet the selected physical feature width before
    # contour extraction. Final contour masks are checked again after rasterization.
    cleaned_labels = regularize_printable_regions(
        labels=label_grid,
        colors=colors,
        pixel_size=config.pixel_size,
        detail_size=config.detail_size,
    )
    # Colors as seen against the image's white (core/white_point.py)
    colors = [tuple(rgb) for rgb in adapt_to_image_white(image, colors).tolist()]
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
