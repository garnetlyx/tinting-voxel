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
    stroke_aspect_ratio_threshold: float = 3.0,
) -> np.ndarray:
    """
    Remove thin features that are below detail_size width, while preserving
    elongated strokes (outlines/borders) that happen to be thin.

    Uses morphological opening to identify sub-threshold thin regions, then
    classifies each connected component of the removed region by aspect ratio:

    - Elongated (aspect_ratio >= stroke_aspect_ratio_threshold): treated as a
      stroke/outline. Dilated back to detail_size width so it survives
      downstream min_area filtering without disappearing.
    - Compact (aspect_ratio < threshold): treated as noise/artifact. Pixels are
      reassigned to the nearest neighbouring label via distance transform.

    This mirrors prior art's thin-region detection + stroke-vs-fill distinction,
    but without requiring full skeleton extraction.

    Args:
        labels: Label grid where each pixel has a label index.
        colors: Color palette for each label.
        pixel_size: Physical size of each pixel in mm.
        detail_size: Minimum feature width in mm (nozzle line width).
        stroke_aspect_ratio_threshold: Bounding-box aspect ratio above which a
            thin component is considered a stroke and preserved.

    Returns:
        Filtered label grid.
    """
    min_width = min_linewidth_pixels_for_detail(pixel_size, detail_size)
    if min_width <= 1:
        return labels.copy()

    import cv2

    height, width = labels.shape
    result = labels.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (min_width, min_width))

    for label_idx in range(len(colors)):
        mask = (labels == label_idx).astype(np.uint8)
        if not mask.any():
            continue

        # Morphological opening: removes features narrower than min_width
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        thin_mask = (mask > 0) & (opened == 0)
        if not thin_mask.any():
            continue

        thin_u8 = thin_mask.astype(np.uint8)
        num_labels, comp_map, stats, _ = cv2.connectedComponentsWithStats(thin_u8, connectivity=8)

        # Accumulate which pixels to keep (strokes) vs. discard (noise)
        stroke_pixels = np.zeros((height, width), dtype=bool)
        noise_pixels = np.zeros((height, width), dtype=bool)

        for comp_id in range(1, num_labels):
            comp_w = int(stats[comp_id, cv2.CC_STAT_WIDTH])
            comp_h = int(stats[comp_id, cv2.CC_STAT_HEIGHT])
            long_side = max(comp_w, comp_h)
            short_side = max(min(comp_w, comp_h), 1)
            aspect_ratio = long_side / short_side

            comp_mask = comp_map == comp_id
            if aspect_ratio >= stroke_aspect_ratio_threshold:
                # Elongated → stroke/outline: dilate to min_width so it
                # passes downstream min_area filtering
                comp_u8 = comp_mask.astype(np.uint8)
                dilated = cv2.dilate(comp_u8, kernel)
                # Only reclaim pixels that still belong to this label in the
                # original mask (don't overwrite other labels)
                stroke_pixels |= (dilated > 0) & (mask > 0)
            else:
                # Compact → noise/artifact: mark for neighbour reassignment
                noise_pixels |= comp_mask

        # Apply stroke preservation: keep these pixels under label_idx
        if stroke_pixels.any():
            result[stroke_pixels] = label_idx

        # Apply noise removal: reassign to nearest other label via distance
        # transform (vectorised, no Python loops)
        if noise_pixels.any():
            # Build a mask of "anchor" pixels: belong to a different label
            # and were not themselves removed
            other_mask = (result != label_idx).astype(np.uint8)
            if not other_mask.any():
                continue
            # Distance transform gives, for each pixel, the distance to the
            # nearest non-zero pixel in other_mask.  We also need the label
            # of that nearest pixel → use label transform via Voronoi.
            # cv2 doesn't expose label transform directly, so we use
            # connectedComponents on other_mask to build a Voronoi map.
            _, voronoi_labels = cv2.distanceTransformWithLabels(
                1 - other_mask,  # foreground = pixels to fill
                cv2.DIST_L2,
                cv2.DIST_MASK_PRECISE,
                labelType=cv2.DIST_LABEL_PIXEL,
            )
            # voronoi_labels[y,x] = flat index of nearest anchor pixel
            # Map flat index → label value in result
            flat_result = result.flatten()
            nearest_label_map = flat_result[voronoi_labels.flatten() - 1].reshape(height, width)
            result[noise_pixels] = nearest_label_map[noise_pixels]

    return result
    
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
