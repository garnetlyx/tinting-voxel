"""
Shared raster connected-component cleanup for pixel and SVG processing.
"""
import math
from typing import Optional, Sequence

import numpy as np
import cv2


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance between two RGB colors in OpenCV's 8-bit Lab space.

    OpenCV's uint8 Lab scales L to 0-255 and offsets a/b by 128, so a unit
    here is not a CIELAB ΔE (black to white measures 255, not 100). The
    color-merge threshold is expressed in these units.
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


def _detail_radius_pixels(pixel_size: float, detail_size: Optional[float]) -> float:
    """Half the selected detail width, in pixels; 0 when every pixel is printable."""
    if detail_size is None or pixel_size >= detail_size:
        return 0.0
    return detail_size / pixel_size / 2.0


def _distance_to(mask: np.ndarray) -> np.ndarray:
    """Euclidean distance from every pixel centre to the nearest ``mask`` pixel centre."""
    return cv2.distanceTransform(
        (~mask).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE,
    )


def printable_coverage(mask: np.ndarray, radius: float) -> np.ndarray:
    """Pixels of ``mask`` that a detail-width bead printed inside it can reach.

    A bead centre fits at a pixel when every non-member pixel square, including
    everything beyond the model edge, is at least ``radius`` away; with
    half-pixel squares that is a centre-to-centre distance of ``radius + 0.5``.
    Slicer perimeters keep convex corners (mitred offsets), so coverage extends
    from those centres by the same reach in the square metric. Any strip, neck,
    or island narrower than the detail width has no bead centre and fails.
    """
    reach = radius + 0.5
    padded = np.pad(mask, 1).astype(np.uint8)
    inside = cv2.distanceTransform(padded, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]
    centres = inside >= reach
    if not centres.any():
        return np.zeros_like(mask)
    side = 2 * int(np.floor(reach)) + 1
    reached = cv2.dilate(centres.astype(np.uint8), np.ones((side, side), np.uint8)) > 0
    return mask & reached


def unprintable_pixels(labels: np.ndarray, radius: float) -> np.ndarray:
    """Pixels whose material region cannot hold a detail-width disk around them."""
    result = np.zeros(labels.shape, dtype=bool)
    if radius <= 0:
        return result
    for label in np.unique(labels):
        mask = labels == label
        result |= mask & ~printable_coverage(mask, radius)
    return result


def _nearest_source_labels(
    labels: np.ndarray, pixels: np.ndarray, sources: np.ndarray,
) -> np.ndarray:
    """Label of the nearest ``sources`` pixel for each ``pixels`` pixel.

    Works on a window around ``pixels`` that grows until every answer is
    provably global: a source outside the window lies beyond the window edge,
    so a nearest distance within the distance to that edge cannot be beaten.
    """
    import scipy.ndimage as ndi

    height, width = labels.shape
    ys, xs = np.nonzero(pixels)
    margin = 8
    while True:
        y0, y1 = max(0, int(ys.min()) - margin), min(height, int(ys.max()) + margin + 1)
        x0, x1 = max(0, int(xs.min()) - margin), min(width, int(xs.max()) + margin + 1)
        if (y1 - y0) * (x1 - x0) * 2 >= height * width:
            # A window this large costs about as much as the whole image.
            y0, y1, x0, x1 = 0, height, 0, width
        window = sources[y0:y1, x0:x1]
        whole = (y0, y1, x0, x1) == (0, height, 0, width)
        if window.any():
            distances, indices = ndi.distance_transform_edt(~window, return_indices=True)
            local_y, local_x = ys - y0, xs - x0
            found = distances[local_y, local_x]
            # Distance from each pixel to the nearest window edge that is not an image edge.
            edge = np.full(len(ys), np.inf)
            if y0 > 0:
                edge = np.minimum(edge, local_y + 1)
            if y1 < height:
                edge = np.minimum(edge, (y1 - y0) - local_y)
            if x0 > 0:
                edge = np.minimum(edge, local_x + 1)
            if x1 < width:
                edge = np.minimum(edge, (x1 - x0) - local_x)
            if whole or np.all(found <= edge):
                return labels[indices[0][local_y, local_x] + y0, indices[1][local_y, local_x] + x0]
        margin *= 2


def _nearest_other_printable_labels(
    labels: np.ndarray, covered: np.ndarray, unresolved: dict[int, np.ndarray],
) -> dict[int, np.ndarray]:
    """For each label's pixels, the label of the nearest printable pixel of another material.

    One distance transform to the nearest printable pixel of any material
    answers every pixel whose nearest printable pixel is already another
    material; only pixels nearest to their own material search again, among
    the other materials, on a window around them. Labels with no printable
    pixel of another material anywhere are omitted.
    """
    import scipy.ndimage as ndi

    if not covered.any():
        return {}
    indices = ndi.distance_transform_edt(~covered, return_distances=False, return_indices=True)
    nearest = labels[indices[0], indices[1]]
    assigned: dict[int, np.ndarray] = {}
    for label, pixels in unresolved.items():
        sources = covered & (labels != label)
        if not sources.any():
            continue
        values = nearest[pixels]
        own = values == label
        if own.any():
            own_pixels = np.zeros_like(pixels)
            own_pixels[pixels] = own
            values[own] = _nearest_source_labels(labels, own_pixels, sources)
        assigned[label] = values
    return assigned


def _widen_or_discard(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    radius: float,
    min_area: int,
    stroke_aspect_ratio_threshold: float = 3.0,
    stroke_fill_density_threshold: float = 0.30,
) -> np.ndarray:
    """One correction pass on the shared label grid.

    Every unprintable component is either a stroke — elongated or sparse and at
    least one detail disk in area, or a connector between two printable parts
    of its material — which is widened to the detail width in place, or noise,
    which joins the most similar color among the printable materials around it
    (the nearest printable material when none is within reach).
    Larger materials yield where widened strokes overlap, so a narrow line is
    not erased by expansion of its background.
    """
    reach = radius + 0.5
    height, width = labels.shape
    result = labels.copy()
    widen: list[tuple[int, int, np.ndarray]] = []
    covered_any = np.zeros(labels.shape, dtype=bool)
    noise_components: list[tuple[int, tuple[int, int, int, int], np.ndarray]] = []
    distance_cache: dict[tuple[int, int], float] = {}
    sizes = dict(zip(*np.unique(labels, return_counts=True)))

    def similarity(first: int, second: int) -> float:
        key = (min(first, second), max(first, second))
        if key not in distance_cache:
            distance_cache[key] = color_distance(colors[key[0]], colors[key[1]])
        return distance_cache[key]

    for label in sizes:
        mask = labels == label
        covered = printable_coverage(mask, radius)
        covered_any |= covered
        thin = mask & ~covered
        if not thin.any():
            continue
        core_count, core_ids = cv2.connectedComponents(covered.astype(np.uint8), connectivity=8)
        count, component_ids, stats, _ = cv2.connectedComponentsWithStats(
            thin.astype(np.uint8), connectivity=8,
        )
        strokes = np.zeros(labels.shape, dtype=bool)
        for component in range(1, count):
            x, y, w, h, area = (int(value) for value in stats[component])
            x0, y0 = max(0, x - 1), max(0, y - 1)
            x1, y1 = min(width, x + w + 1), min(height, y + h + 1)
            local = component_ids[y0:y1, x0:x1] == component
            aspect_ratio = max(w, h) / max(min(w, h), 1)
            fill_density = area / max(w * h, 1)
            is_stroke = area >= min_area and (
                aspect_ratio >= stroke_aspect_ratio_threshold
                or fill_density <= stroke_fill_density_threshold
            )
            if not is_stroke and core_count > 2:
                bordering = cv2.dilate(local.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
                touching = np.unique(core_ids[y0:y1, x0:x1][bordering])
                is_stroke = np.count_nonzero(touching) >= 2
            if is_stroke:
                strokes[y0:y1, x0:x1] |= local
            else:
                noise_components.append((int(label), (y0, y1, x0, x1), local))
        if strokes.any():
            widen.append((int(sizes[label]), int(label), strokes))

    margin = int(np.ceil(reach)) + 1
    dominant = max(sizes, key=lambda label: (sizes[label], -int(label)))
    unresolved: dict[int, np.ndarray] = {}
    for label, (y0, y1, x0, x1), local in noise_components:
        ny0, ny1 = max(0, y0 - margin), min(height, y1 + margin)
        nx0, nx1 = max(0, x0 - margin), min(width, x1 + margin)
        component = np.zeros((ny1 - ny0, nx1 - nx0), dtype=bool)
        component[y0 - ny0:y1 - ny0, x0 - nx0:x1 - nx0] = local
        near = _distance_to(component) <= reach + 1
        window = labels[ny0:ny1, nx0:nx1]
        candidates = np.unique(window[near & covered_any[ny0:ny1, nx0:nx1] & (window != label)])
        if len(candidates):
            result[y0:y1, x0:x1][local] = min(
                candidates, key=lambda other: (similarity(label, int(other)), -sizes[other], int(other)),
            )
        else:
            pending = unresolved.setdefault(label, np.zeros(labels.shape, dtype=bool))
            pending[y0:y1, x0:x1] |= local
    assigned = _nearest_other_printable_labels(labels, covered_any, unresolved)
    for label, pixels in unresolved.items():
        if label in assigned:
            result[pixels] = assigned[label]
        elif label != dominant:
            # Nothing anywhere is printable yet: the largest material absorbs the rest.
            result[pixels] = dominant

    for _, label, strokes in sorted(widen, reverse=True):
        result[_distance_to(strokes) <= reach] = label
    return result


def _absorb_into_surrounding(labels: np.ndarray, failing: np.ndarray) -> np.ndarray:
    """Give each failing patch, across all its labels, the dominant passing label around it."""
    height, width = labels.shape
    result = labels.copy()
    ring = np.ones((3, 3), np.uint8)
    count, component_ids, stats, _ = cv2.connectedComponentsWithStats(
        failing.astype(np.uint8), connectivity=8,
    )
    for component in range(1, count):
        x, y, w, h, _ = (int(value) for value in stats[component])
        y0, y1 = max(0, y - 1), min(height, y + h + 1)
        x0, x1 = max(0, x - 1), min(width, x + w + 1)
        patch = component_ids[y0:y1, x0:x1] == component
        border = (cv2.dilate(patch.astype(np.uint8), ring) > 0) & ~failing[y0:y1, x0:x1]
        if not border.any():
            continue
        values, counts = np.unique(labels[y0:y1, x0:x1][border], return_counts=True)
        result[y0:y1, x0:x1][patch] = values[np.argmax(counts)]
    return result


def regularize_printable_regions(
    labels: np.ndarray,
    colors: Sequence[tuple[int, int, int]],
    pixel_size: float,
    detail_size: Optional[float],
    max_passes: int = 12,
) -> np.ndarray:
    """Make every material region printable at the selected detail width.

    The grid's dimensions and physical pixel pitch stay unchanged. Sub-detail
    strokes are widened and noise joins the most similar surrounding color
    until every pixel lies under a detail-width disk of its own material.
    Patches still failing after the correction passes join the material that
    dominates their printable border.
    """
    radius = _detail_radius_pixels(pixel_size, detail_size)
    if radius <= 0:
        return labels.copy()
    if min(labels.shape) < 2 * radius:
        raise ValueError(
            f"Model's shorter side ({min(labels.shape) * pixel_size:.2f} mm) is "
            f"smaller than the selected detail width ({detail_size:.2f} mm). "
            "Increase the model size or choose a smaller detail width."
        )

    min_area = min_region_pixels_for_detail(pixel_size, detail_size)
    current = labels.copy()
    failing = unprintable_pixels(current, radius)
    best, best_failing = current, failing
    passes_without_progress = 0
    for _ in range(max_passes):
        if not failing.any():
            return current
        current = _widen_or_discard(current, colors, radius, min_area)
        failing = unprintable_pixels(current, radius)
        if failing.sum() < 0.95 * best_failing.sum():
            passes_without_progress = 0
        else:
            passes_without_progress += 1
        if failing.sum() <= best_failing.sum():
            best, best_failing = current, failing
        if passes_without_progress >= 2:
            break
    current, failing = best, best_failing

    # Competing strokes can trade the last few pixels back and forth. Each
    # remaining patch joins the material that dominates its printable border.
    for _ in range(max_passes):
        if not failing.any():
            break
        corrected = _absorb_into_surrounding(current, failing)
        if np.array_equal(corrected, current):
            break
        current = corrected
        failing = unprintable_pixels(current, radius)
    return current
