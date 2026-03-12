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

        fallback_candidates = [
            component for component in sorted(
                small_components,
                key=lambda item: (len(item['pixels']), min((py, px) for px, py in item['pixels'])),
            )
            if component['neighbor_component_ids']
        ]
        if not fallback_candidates:
            return finalize(current_labels, "Stopping small region cleanup; no eligible merge targets remain")

        component = fallback_candidates[0]
        neighbor_components = [
            components[neighbor_id]
            for neighbor_id in component['neighbor_component_ids']
        ]
        best_neighbor = min(
            neighbor_components,
            key=lambda candidate: (
                color_distance(component['rgb'], candidate['rgb']),
                -candidate['size'],
                candidate['component_id'],
            ),
        )
        for x, y in component['pixels']:
            current_labels[y, x] = best_neighbor['label']
        total_fallback_merged += 1
        logger.info(
            "Small region cleanup round %d: fallback merged one undersized component into neighbor %d",
            round_idx,
            best_neighbor['component_id'],
        )
