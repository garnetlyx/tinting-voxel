"""
Shared raster connected-component cleanup for pixel and SVG processing.
"""
import logging
import math
import time
from typing import Optional, Sequence

import numpy as np
import cv2

logger = logging.getLogger(__name__)


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate perceptual distance between two RGB colors using CIELAB space.

    CIELAB is a perceptually uniform color space where equal numerical
    distances correspond to equal perceived color differences, unlike RGB
    Euclidean distance which is not perceptually uniform.
    """
    rgb1 = np.array([[list(c1)]], dtype=np.uint8)
    rgb2 = np.array([[list(c2)]], dtype=np.uint8)
    lab1 = cv2.cvtColor(rgb1, cv2.COLOR_RGB2Lab)[0, 0].astype(float)
    lab2 = cv2.cvtColor(rgb2, cv2.COLOR_RGB2Lab)[0, 0].astype(float)
    return float(np.sqrt(np.sum((lab1 - lab2) ** 2)))


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
    stroke_fill_density_threshold: float = 0.30,
) -> np.ndarray:
    """Resolve sub-detail-width material regions without changing model size.

    Large or core-connecting strokes gain real cells in the shared label grid;
    compact sub-threshold noise is reassigned to nearby material. Materials are
    classified on the same input grid before overlapping expansions are settled.
    """
    min_width = min_linewidth_pixels_for_detail(pixel_size, detail_size)
    if min_width <= 1:
        return labels.copy()
    min_area = min_region_pixels_for_detail(pixel_size, detail_size)
    if labels.size < min_area:
        return labels.copy()

    height, width = labels.shape
    result = labels.copy()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (min_width, min_width))
    strokes: list[tuple[int, int, np.ndarray]] = []

    for label_idx in range(len(colors)):
        mask = (labels == label_idx).astype(np.uint8)
        if not mask.any():
            continue

        # Morphological opening: removes features narrower than min_width
        opened = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN, kernel,
            borderType=cv2.BORDER_CONSTANT, borderValue=0,
        )
        thin_all = (mask > 0) & (opened == 0)
        thin_mask = thin_all.copy()
        bridge_pixels = np.zeros_like(thin_all)
        if opened.any():
            core_halo = cv2.dilate(opened, kernel) > 0
            thin_mask &= ~core_halo

            # A narrow connector between two printable cores must remain
            # intact. The halo rule above would otherwise break it at both
            # ends, leaving sub-nozzle stubs in the exported material.
            core_count, core_ids = cv2.connectedComponents(opened, connectivity=8)
            if core_count > 2:
                component_count, component_ids, component_stats, _ = cv2.connectedComponentsWithStats(
                    thin_all.astype(np.uint8), connectivity=8,
                )
                for component_id in range(1, component_count):
                    x, y, component_width, component_height, _ = component_stats[component_id]
                    if max(component_width, component_height) < min_width:
                        continue
                    x0, y0 = max(0, x - 1), max(0, y - 1)
                    x1, y1 = min(width, x + component_width + 1), min(height, y + component_height + 1)
                    region = component_ids[y0:y1, x0:x1] == component_id
                    bordering = cv2.dilate(region.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
                    touching = np.unique(core_ids[y0:y1, x0:x1][bordering])
                    if np.count_nonzero(touching) >= 2:
                        thin_mask[y0:y1, x0:x1] |= region
                        bridge_pixels[y0:y1, x0:x1] |= region
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

            # Fill density: fraction of bounding box actually occupied by pixels.
            # A connected network of thin lines (e.g. stained-glass border) spans
            # a large bounding box but fills only a small fraction of it.
            pixel_count = int(stats[comp_id, cv2.CC_STAT_AREA])
            bbox_area = max(comp_w * comp_h, 1)
            fill_density = pixel_count / bbox_area

            comp_mask = comp_map == comp_id
            is_stroke = (
                aspect_ratio >= stroke_aspect_ratio_threshold
                or fill_density <= stroke_fill_density_threshold
            )
            is_bridge = bool(np.any(comp_mask & bridge_pixels))
            if (is_stroke and (pixel_count >= min_area or is_bridge)) or (
                pixel_count >= min_area and short_side < min_width
            ):
                # Stroke/outline (individual line OR sparse connected network):
                # dilate to min_width so it passes downstream min_area filtering.
                comp_u8 = comp_mask.astype(np.uint8)
                dilated = cv2.dilate(comp_u8, kernel)
                # A sub-nozzle-width stroke cannot be printed merely by
                # retaining its original pixels. Give it real physical width
                # in the label grid; neighbouring labels yield those cells.
                stroke_pixels |= dilated > 0
            elif pixel_count < min_area:
                # Compact → noise/artifact: mark for neighbour reassignment
                noise_pixels |= comp_mask

        # Classify against the original partition. In-place expansion would
        # erase another material's thin bridge before it can be recognized.
        if stroke_pixels.any():
            strokes.append((int(mask.sum()), label_idx, stroke_pixels))

        # Apply noise removal: reassign to nearest other label via exact distance transform
        if noise_pixels.any():
            # Build a mask of "anchor" pixels: belong to a different label
            # and were not themselves removed
            other_mask = (result != label_idx).astype(np.uint8)
            if not other_mask.any():
                continue
            import scipy.ndimage as ndi
            # distance_transform_edt returns the exact (y, x) coordinates of the
            # nearest zero pixel in (1 - other_mask), i.e., the nearest anchor pixel
            indices = ndi.distance_transform_edt(
                1 - other_mask,
                return_distances=False,
                return_indices=True,
            )
            result[noise_pixels] = result[indices[0][noise_pixels], indices[1][noise_pixels]]

    # Larger regions yield in overlaps, so a narrow line is not erased by
    # adjacent background expansion. Ties retain palette order.
    for _, label_idx, stroke_pixels in sorted(strokes, reverse=True):
        result[stroke_pixels] = label_idx

    return result


def regularize_printable_regions(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    pixel_size: float,
    detail_size: Optional[float],
) -> np.ndarray:
    """Widen retained strokes and merge noise on the final physical pixel grid.

    Widening one material can expose a narrow remnant of another material.
    Re-evaluate the shared label grid after each material-width correction;
    the grid's dimensions and physical pixel pitch remain unchanged.
    """
    min_width = min_linewidth_pixels_for_detail(pixel_size, detail_size)
    if min_width <= 1:
        return labels.copy()
    if min(labels.shape) < min_width:
        raise ValueError(
            f"Model's shorter side ({min(labels.shape) * pixel_size:.2f} mm) is "
            f"smaller than the selected detail width ({detail_size:.2f} mm). "
            "Increase the model size or choose a smaller detail width."
        )

    min_area = min_region_pixels_for_detail(pixel_size, detail_size)

    def narrow_region_count(grid: np.ndarray) -> int:
        count = 0
        for label in np.unique(grid):
            components, _, stats, _ = cv2.connectedComponentsWithStats(
                (grid == label).astype(np.uint8), connectivity=4,
            )
            if components <= 1:
                continue
            regions = stats[1:]
            count += int(np.count_nonzero(
                (regions[:, cv2.CC_STAT_AREA] >= min_area)
                & (
                    (regions[:, cv2.CC_STAT_WIDTH] < min_width)
                    | (regions[:, cv2.CC_STAT_HEIGHT] < min_width)
                )
            ))
        return count

    current = labels.copy()
    best = current
    fewest_remaining = math.inf
    for _ in range(min_width * len(colors)):
        widened = remove_thin_features(current, colors, pixel_size, detail_size)
        cleaned = merge_small_label_regions(widened, colors, pixel_size, detail_size)
        remaining = narrow_region_count(cleaned)
        if remaining < fewest_remaining:
            best, fewest_remaining = cleaned, remaining
        if remaining == 0:
            return cleaned
        if np.array_equal(cleaned, current):
            break
        current = cleaned
    return best


def merge_small_label_regions(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    pixel_size: float,
    detail_size: Optional[float],
) -> np.ndarray:
    """Merge sub-threshold 4-connected regions into touching neighboring labels.

    Component IDs retain row-major first-pixel order. This preserves the
    existing size and color tie-breaks while connected-component discovery and
    pixel reassignment run in NumPy/OpenCV rather than Python per pixel.
    """
    min_region_pixels = min_region_pixels_for_detail(pixel_size, detail_size)
    if min_region_pixels <= 1:
        return labels.copy()

    current_labels = labels.copy()
    started_at = time.perf_counter()
    round_idx = 0
    total_batch_merged = 0
    total_fallback_merged = 0
    distance_cache: dict[tuple[int, int], float] = {}

    logger.info(
        "Merging small raster regions: pixel_size=%.2fmm, detail_size=%.2fmm, min_region=%d pixels",
        pixel_size,
        detail_size,
        min_region_pixels,
    )

    def finalize(result: np.ndarray, message: str) -> np.ndarray:
        logger.info(
            "%s after %d rounds (batch_merged=%d, fallback_merged=%d, elapsed=%.3fs)",
            message,
            round_idx,
            total_batch_merged,
            total_fallback_merged,
            time.perf_counter() - started_at,
        )
        return result

    def label_distance(first_label: int, second_label: int) -> float:
        key = (min(first_label, second_label), max(first_label, second_label))
        if key not in distance_cache:
            distance_cache[key] = color_distance(colors[key[0]], colors[key[1]])
        return distance_cache[key]

    while True:
        height, width = current_labels.shape
        temporary_ids = np.full((height, width), -1, dtype=np.int32)
        records: list[tuple[int, int, int]] = []  # label, area, first pixel index

        for label in np.unique(current_labels):
            mask = current_labels == label
            count, local_ids, stats, _ = cv2.connectedComponentsWithStats(
                mask.astype(np.uint8), connectivity=4,
            )
            if count <= 1:
                continue

            # OpenCV's IDs group one color; globally restore the prior scan
            # order, including the case where this color fills the whole image.
            present_ids, positions = np.unique(local_ids, return_index=True)
            first_positions = np.full(count, -1, dtype=np.int64)
            first_positions[present_ids] = positions
            base_id = len(records)
            temporary_ids[mask] = base_id + local_ids[mask] - 1
            for local_id in range(1, count):
                records.append((
                    int(label),
                    int(stats[local_id, cv2.CC_STAT_AREA]),
                    int(first_positions[local_id]),
                ))

        if not records:
            return finalize(current_labels, "Small region cleanup stabilized")

        order = np.argsort([record[2] for record in records], kind="stable")
        rank = np.empty(len(records), dtype=np.int32)
        rank[order] = np.arange(len(records), dtype=np.int32)
        component_ids = rank[temporary_ids]
        components = [records[index] for index in order]
        component_labels = np.asarray([item[0] for item in components], dtype=current_labels.dtype)
        component_sizes = np.asarray([item[1] for item in components], dtype=np.int32)
        first_positions = np.asarray([item[2] for item in components], dtype=np.int64)
        small_ids = np.flatnonzero(component_sizes < min_region_pixels)
        if len(small_ids) == 0:
            return finalize(current_labels, "Small region cleanup stabilized")

        # Every edge between different component IDs is a 4-neighbor contact.
        # Deduplicate before building each component's neighbor set.
        edge_parts = []
        for side_a, side_b in (
            (component_ids[:, :-1], component_ids[:, 1:]),
            (component_ids[:-1, :], component_ids[1:, :]),
        ):
            boundary = side_a != side_b
            if np.any(boundary):
                edge_parts.append(np.stack((side_a[boundary], side_b[boundary]), axis=1))
        neighbors: list[set[int]] = [set() for _ in components]
        if edge_parts:
            edges = np.unique(
                np.sort(np.concatenate(edge_parts, axis=0), axis=1), axis=0,
            )
            for first_id, second_id in edges:
                first_id, second_id = int(first_id), int(second_id)
                neighbors[first_id].add(second_id)
                neighbors[second_id].add(first_id)

        round_idx += 1
        logger.info(
            "Small region cleanup round %d: found %d undersized components",
            round_idx,
            len(small_ids),
        )
        stable_ids = set(np.flatnonzero(component_sizes >= min_region_pixels).tolist())
        batch_assignments: dict[int, int] = {}
        for component_id in sorted(
            small_ids.tolist(),
            key=lambda index: (component_sizes[index], first_positions[index]),
        ):
            stable_neighbors = [
                candidate for candidate in neighbors[component_id]
                if candidate in stable_ids
            ]
            if not stable_neighbors:
                continue
            best_neighbor = min(
                stable_neighbors,
                key=lambda candidate: (
                    label_distance(
                        int(component_labels[component_id]),
                        int(component_labels[candidate]),
                    ),
                    -component_sizes[candidate],
                    candidate,
                ),
            )
            batch_assignments[component_id] = int(component_labels[best_neighbor])

        if batch_assignments:
            next_labels = component_labels.copy()
            for component_id, target_label in batch_assignments.items():
                next_labels[component_id] = target_label
            current_labels = next_labels[component_ids]
            total_batch_merged += len(batch_assignments)
            logger.info(
                "Small region cleanup round %d: batch merged %d undersized components into stable neighbors",
                round_idx,
                len(batch_assignments),
            )
            continue

        if not any(neighbors[component_id] for component_id in small_ids):
            return finalize(current_labels, "Stopping small region cleanup; no eligible merge targets remain")

        best_neighbor_by_component: dict[int, int] = {}
        for component_id in small_ids.tolist():
            if not neighbors[component_id]:
                continue
            best_neighbor_by_component[component_id] = min(
                neighbors[component_id],
                key=lambda candidate: (
                    label_distance(
                        int(component_labels[component_id]),
                        int(component_labels[candidate]),
                    ),
                    -component_sizes[candidate],
                    candidate,
                ),
            )

        resolved_representatives: dict[int, int] = {}
        for component_id in best_neighbor_by_component:
            if component_id in resolved_representatives:
                continue
            path: list[int] = []
            seen_at: dict[int, int] = {}
            current_id = component_id
            while True:
                if current_id in resolved_representatives:
                    representative = resolved_representatives[current_id]
                    break
                if current_id in seen_at:
                    cycle_ids = path[seen_at[current_id]:]
                    representative = min(
                        cycle_ids,
                        key=lambda index: (-component_sizes[index], index),
                    )
                    break
                seen_at[current_id] = len(path)
                path.append(current_id)
                next_id = best_neighbor_by_component.get(current_id)
                if next_id is None:
                    representative = current_id
                    break
                current_id = next_id
            for path_id in path:
                resolved_representatives[path_id] = representative

        next_labels = component_labels.copy()
        fallback_merge_count = 0
        for component_id in small_ids.tolist():
            representative = resolved_representatives.get(component_id, component_id)
            if representative != component_id:
                next_labels[component_id] = component_labels[representative]
                fallback_merge_count += 1
        if fallback_merge_count == 0:
            return finalize(current_labels, "Stopping small region cleanup; fallback could not reduce undersized regions")
        current_labels = next_labels[component_ids]
        total_fallback_merged += fallback_merge_count
        logger.info(
            "Small region cleanup round %d: fallback batch merged %d undersized components without stable neighbors",
            round_idx,
            fallback_merge_count,
        )
