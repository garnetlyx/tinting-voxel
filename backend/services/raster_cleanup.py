"""
Shared raster connected-component cleanup for pixel and SVG processing.
"""
import logging
import math
import time
from typing import Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate Euclidean distance between two RGB colors."""
    return float(np.sqrt(
        (c1[0] - c2[0]) ** 2 +
        (c1[1] - c2[1]) ** 2 +
        (c1[2] - c2[2]) ** 2
    ))


def min_region_pixels_for_detail(pixel_size: float, detail_size: Optional[float]) -> int:
    """Return the minimum legal connected-component size in pixels."""
    if detail_size is None or pixel_size >= detail_size:
        return 1
    scale_factor = detail_size / pixel_size
    return math.ceil(scale_factor * scale_factor)


def min_linewidth_pixels_for_detail(pixel_size: float, detail_size: Optional[float]) -> int:
    """
    Return the minimum line width in pixels based on detail_size.
    
    This is used for morphological filtering to remove thin features
    that would be unprintable with typical nozzle sizes.
    """
    if detail_size is None or pixel_size >= detail_size:
        return 1
    # Linear relationship: detail_size / pixel_size
    return max(1, int(np.ceil(detail_size / pixel_size)))


def remove_thin_features(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    pixel_size: float,
    detail_size: Optional[float],
) -> np.ndarray:
    """
    Remove thin features (narrow lines/edges) that are below detail_size width.
    
    Uses morphological opening to filter out features narrower than the threshold.
    This is important for 3D printing where thin features may be unprintable
    with the nozzle diameter.
    
    Args:
        labels: Label grid where each pixel has a label index
        colors: Color palette for each label
        pixel_size: Physical size of each pixel in mm
        detail_size: Minimum feature width in mm
    
    Returns:
        Filtered label grid with thin features removed
    """
    min_width = min_linewidth_pixels_for_detail(pixel_size, detail_size)
    if min_width <= 1:
        return labels.copy()
    
    import cv2
    
    height, width = labels.shape
    result = labels.copy()
    
    # Process each label separately
    for label_idx in range(len(colors)):
        # Create binary mask for this label
        mask = (labels == label_idx).astype(np.uint8)
        
        if not mask.any():
            continue
        
        # Morphological opening: erosion followed by dilation
        # This removes features thinner than the kernel size
        kernel_size = min_width
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        # Opening removes thin features
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # Find pixels that were removed by opening
        removed_pixels = (mask > 0) & (opened == 0)
        
        if not removed_pixels.any():
            continue
        
        # For removed pixels, assign to nearest neighbor of different label
        removed_coords = np.argwhere(removed_pixels)
        
        for y, x in removed_coords:
            # Find nearest non-removed pixel with different label
            min_dist = float('inf')
            nearest_label = label_idx
            
            # Search in a small neighborhood
            search_radius = min_width * 2
            y_min = max(0, y - search_radius)
            y_max = min(height, y + search_radius + 1)
            x_min = max(0, x - search_radius)
            x_max = min(width, x + search_radius + 1)
            
            for ny in range(y_min, y_max):
                for nx in range(x_min, x_max):
                    if result[ny, nx] != label_idx:
                        dist = np.sqrt((ny - y)**2 + (nx - x)**2)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_label = result[ny, nx]
            
            result[y, x] = nearest_label
    
    return result


def merge_small_label_regions(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    pixel_size: float,
    detail_size: Optional[float],
) -> np.ndarray:
    """
    Merge sub-threshold connected components into touching neighboring labels.

    The label grid is assumed to be dense: every pixel belongs to exactly one label.
    """
    min_region_pixels = min_region_pixels_for_detail(pixel_size, detail_size)
    if min_region_pixels <= 1:
        return labels.copy()

    height, width = labels.shape
    current_labels = labels.copy()
    started_at = time.perf_counter()
    total_batch_merged = 0
    total_fallback_merged = 0

    logger.info(
        "Merging small raster regions: pixel_size=%.2fmm, detail_size=%.2fmm, min_region=%d pixels",
        pixel_size,
        detail_size,
        min_region_pixels,
    )

    def finalize(result: np.ndarray, message: str) -> np.ndarray:
        elapsed = time.perf_counter() - started_at
        logger.info(
            "%s after %d rounds (batch_merged=%d, fallback_merged=%d, elapsed=%.3fs)",
            message,
            round_idx,
            total_batch_merged,
            total_fallback_merged,
            elapsed,
        )
        return result

    def get_neighbors(x: int, y: int) -> list[tuple[int, int]]:
        neighbors = []
        for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if 0 <= nx < width and 0 <= ny < height:
                neighbors.append((nx, ny))
        return neighbors

    def build_components(label_grid: np.ndarray) -> tuple[list[dict], np.ndarray]:
        visited = np.zeros((height, width), dtype=bool)
        component_ids = np.full((height, width), -1, dtype=np.int32)
        components: list[dict] = []

        for y in range(height):
            for x in range(width):
                if visited[y, x]:
                    continue

                label = int(label_grid[y, x])
                stack = [(x, y)]
                component_pixels: list[tuple[int, int]] = []

                while stack:
                    cx, cy = stack.pop()
                    if visited[cy, cx]:
                        continue
                    if int(label_grid[cy, cx]) != label:
                        continue

                    visited[cy, cx] = True
                    component_ids[cy, cx] = len(components)
                    component_pixels.append((cx, cy))

                    for nx, ny in get_neighbors(cx, cy):
                        if not visited[ny, nx]:
                            stack.append((nx, ny))

                components.append({
                    'component_id': len(components),
                    'label': label,
                    'pixels': component_pixels,
                    'size': len(component_pixels),
                    'rgb': tuple(int(channel) for channel in colors[label]),
                    'neighbor_component_ids': set(),
                })

        for component in components:
            for x, y in component['pixels']:
                for nx, ny in get_neighbors(x, y):
                    neighbor_component_id = int(component_ids[ny, nx])
                    if neighbor_component_id != component['component_id']:
                        component['neighbor_component_ids'].add(neighbor_component_id)

        return components, component_ids

    round_idx = 0
    while True:
        components, _component_ids = build_components(current_labels)
        small_components = [
            component
            for component in components
            if component['size'] < min_region_pixels
        ]

        if not small_components:
            return finalize(current_labels, "Small region cleanup stabilized")

        round_idx += 1
        stable_component_ids = {
            component['component_id']
            for component in components
            if component['size'] >= min_region_pixels
        }
        logger.info(
            "Small region cleanup round %d: found %d undersized components",
            round_idx,
            len(small_components),
        )

        batch_assignments: list[tuple[dict, dict]] = []
        for component in sorted(
            small_components,
            key=lambda item: (len(item['pixels']), min((py, px) for px, py in item['pixels'])),
        ):
            stable_neighbors = [
                components[neighbor_id]
                for neighbor_id in component['neighbor_component_ids']
                if neighbor_id in stable_component_ids
            ]
            if not stable_neighbors:
                continue

            best_neighbor = min(
                stable_neighbors,
                key=lambda candidate: (
                    color_distance(component['rgb'], candidate['rgb']),
                    -candidate['size'],
                    candidate['component_id'],
                ),
            )
            batch_assignments.append((component, best_neighbor))

        if batch_assignments:
            for component, best_neighbor in batch_assignments:
                for x, y in component['pixels']:
                    current_labels[y, x] = best_neighbor['label']
            total_batch_merged += len(batch_assignments)
            logger.info(
                "Small region cleanup round %d: batch merged %d undersized components into stable neighbors",
                round_idx,
                len(batch_assignments),
            )
            continue

        if not any(component['neighbor_component_ids'] for component in small_components):
            return finalize(current_labels, "Stopping small region cleanup; no eligible merge targets remain")

        best_neighbor_by_component: dict[int, dict] = {}
        for component in small_components:
            if not component['neighbor_component_ids']:
                continue
            neighbor_components = [
                components[neighbor_id]
                for neighbor_id in component['neighbor_component_ids']
            ]
            best_neighbor_by_component[component['component_id']] = min(
                neighbor_components,
                key=lambda candidate: (
                    color_distance(component['rgb'], candidate['rgb']),
                    -candidate['size'],
                    candidate['component_id'],
                ),
            )

        resolved_representatives: dict[int, int] = {}

        def cycle_representative(component_ids: list[int]) -> int:
            return min(
                component_ids,
                key=lambda component_id: (
                    -components[component_id]['size'],
                    component_id,
                ),
            )

        for component_id in best_neighbor_by_component:
            if component_id in resolved_representatives:
                continue

            path: list[int] = []
            seen_at: dict[int, int] = {}
            current_component_id = component_id

            while True:
                if current_component_id in resolved_representatives:
                    representative = resolved_representatives[current_component_id]
                    break
                if current_component_id in seen_at:
                    cycle_ids = path[seen_at[current_component_id]:]
                    representative = cycle_representative(cycle_ids)
                    break

                seen_at[current_component_id] = len(path)
                path.append(current_component_id)
                next_component = best_neighbor_by_component.get(current_component_id)
                if next_component is None:
                    representative = current_component_id
                    break
                current_component_id = next_component['component_id']

            for path_component_id in path:
                resolved_representatives[path_component_id] = representative

        fallback_merge_count = 0
        for component in small_components:
            representative_id = resolved_representatives.get(component['component_id'], component['component_id'])
            if representative_id == component['component_id']:
                continue

            representative = components[representative_id]
            for x, y in component['pixels']:
                current_labels[y, x] = representative['label']
            fallback_merge_count += 1

        if fallback_merge_count == 0:
            return finalize(current_labels, "Stopping small region cleanup; fallback could not reduce undersized regions")

        total_fallback_merged += fallback_merge_count
        logger.info(
            "Small region cleanup round %d: fallback batch merged %d undersized components without stable neighbors",
            round_idx,
            fallback_merge_count,
        )
