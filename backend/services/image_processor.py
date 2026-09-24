"""
Image processing service for color extraction and clustering
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
from config.settings import settings
import base64
import logging
import math
import threading
import weakref
from collections import OrderedDict
from io import BytesIO
from typing import Optional

import numpy as np
import cv2
from PIL import Image

from core.blend_color import Colors, colors_key
from core.color_materials import Color
from services.print_stack import build_print_stack, resolve_backing_label
from services.label_map import EMPTY, block_cell_counts, block_pixels
from services.raster_cleanup import color_distance, regularize_printable_regions
from services.stl_generator import compute_reference_matrices

logger = logging.getLogger(__name__)

# Safety cap only — prevents truly pathological inputs (e.g. 100MP raw photos).
# Normal photos are processed at full resolution; pixelSize controls physical output size.
MAX_PROCESSING_DIMENSION = 4096
# Unique-color count at or below which merge_similar_colors runs the exact
# O(n²) path without the lossy 5-bit bucket pre-quantization. Above it
# (natural-photo scale) the pre-quantization engages to bound the merge cost.
EXACT_MERGE_MAX_UNIQUE = 4096
# Unique colors per slice when assigning them to the final colors.
NEAREST_FINAL_CHUNK = 65_536
# Mapping results kept per reference matrix, so exports and preview refreshes
# reuse the mapping processing already computed. Entries are keyed by the
# matrix object and removed with it (matrices live in services/matrix_cache).
MAPPINGS_PER_MATRIX = 16
_mapping_cache: dict[int, OrderedDict] = {}
_mapping_lock = threading.Lock()


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _image_to_data_url(img: Image.Image) -> str:
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


def _render_labels(labels: np.ndarray, block_rgbs: list[tuple[int, int, int]]) -> str:
    """PNG data URL of a label map painted with one color per block (black where empty)."""
    lut = np.zeros((EMPTY + 1, 3), dtype=np.uint8)
    lut[:len(block_rgbs)] = block_rgbs
    return _image_to_data_url(Image.fromarray(lut[labels]))


def _map_and_refine(
    source_colors: list[tuple[int, int, int]],
    ref_code_matrix,
    ref_rgb_matrix,
    colors: Colors,
    layer_count: int,
    layer_height: float,
    backing_suffix: str = '',
    background_rgb: Optional[tuple] = None,
) -> tuple[list[str], list[tuple[int, int, int]]]:
    """Nearest-code mapping plus order refinement for pruned (translucent) sets.

    The matrices must already be backing-aware when a printed backing block is
    configured (same suffix/boundary); the returned codes carry the backing
    as a trailing suffix — the physical stack that actually prints."""
    from core.stack_prune import refine_matches
    from services.stl_generator import _build_codes_to_rgb

    mappings = _matrix_mappings(ref_code_matrix)
    key = (
        tuple(tuple(int(channel) for channel in rgb) for rgb in source_colors),
        colors_key(colors), layer_count, layer_height, backing_suffix,
        None if background_rgb is None else tuple(background_rgb),
    )
    with _mapping_lock:
        cached = mappings.get(key)
        if cached is not None:
            mappings.move_to_end(key)
    if cached is not None:
        return list(cached[0]), list(cached[1])

    result_codes, result_rgbs = Color.map_to_nearest_color(
        source_colors, ref_code_matrix, ref_rgb_matrix,
    )
    result_codes, result_rgbs = refine_matches(
        source_colors,
        result_codes,
        result_rgbs,
        ref_code_matrix,
        ref_rgb_matrix,
        colors,
        layer_height,
        codes_to_rgb=_build_codes_to_rgb(
            colors, layer_count, layer_height,
            backing_suffix=backing_suffix, background_rgb=background_rgb,
        ),
    )
    normalized_rgbs = [
        tuple(int(channel) for channel in np.asarray(rgb).tolist())
        for rgb in result_rgbs
    ]
    codes = [code + backing_suffix for code in result_codes]
    with _mapping_lock:
        mappings[key] = (tuple(codes), tuple(normalized_rgbs))
        while len(mappings) > MAPPINGS_PER_MATRIX:
            mappings.popitem(last=False)
    return codes, normalized_rgbs


def _matrix_mappings(ref_code_matrix) -> OrderedDict:
    """The mapping results cached for this reference matrix."""
    matrix_id = id(ref_code_matrix)
    with _mapping_lock:
        mappings = _mapping_cache.get(matrix_id)
        if mappings is None:
            mappings = _mapping_cache[matrix_id] = OrderedDict()
            # Drop the entry with its matrix, before the id can be reused.
            weakref.finalize(ref_code_matrix, _mapping_cache.pop, matrix_id, None)
    return mappings


def _map_source_colors_to_blends(
    source_colors: list[tuple[int, int, int]],
    colors: Colors,
    layer_count: int,
    layer_height: float,
    backing_layers: Optional[int] = None,
    backing_mode: str = 'white',
) -> tuple[list[str], list[tuple[int, int, int]]]:
    from services.print_stack import (
        PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label,
    )
    b_label = resolve_backing_label(colors, backing_layers, backing_mode)
    b_suffix = backing_suffix(b_label, backing_layers)
    b_boundary = PRINT_BACKGROUND_RGB if b_suffix else None
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count,
        layer_height,
        colors,
        n_targets=len(source_colors),
        backing_layers=backing_layers,
        backing_mode=backing_mode,
    )
    return _map_and_refine(
        source_colors, ref_code_matrix, ref_rgb_matrix, colors, layer_count, layer_height,
        backing_suffix=b_suffix, background_rgb=b_boundary,
    )


def _build_mapped_blend_palette(
    entries: list[dict],
    result_codes: list[str],
    result_rgbs: list[tuple[int, int, int]],
    total_pixels: int,
) -> list[dict]:
    mapped_blend_palette = []
    for entry, code, rgb in zip(entries, result_codes, result_rgbs):
        source_rgb = (
            int(entry['r']),
            int(entry['g']),
            int(entry['b']),
        )
        pixel_count = int(entry['pixelCount'])
        if pixel_count == 0:
            continue
        mapped_blend_palette.append({
            "code": code,
            "rgb": list(rgb),
            "hex": _rgb_to_hex(rgb),
            "sourceRgb": list(source_rgb),
            "sourceHex": _rgb_to_hex(source_rgb),
            "pixelCount": pixel_count,
            "pixelPercent": round(pixel_count * 100.0 / total_pixels, 4),
        })

    mapped_blend_palette.sort(key=lambda entry: entry["pixelCount"], reverse=True)
    return mapped_blend_palette


def build_simulated_print_preview(
    color_blocks: list[dict],
    labels: np.ndarray,
    colors: Optional[Colors] = None,
    layer_count: int = 4,
    layer_height: float = 0.08,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
) -> dict:
    """
    Build an image-specific print preview from current color blocks
    (block i covers the cells where labels == i).

    The preview uses the same nearest printable blend mapping as STL export.
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    active_colors = colors or Colors()
    resolve_backing_label(active_colors, white_backing_layers, backing_mode)
    counts = block_cell_counts(labels, len(color_blocks))
    total_pixels = max(1, int(counts.sum()))

    source_entries = [
        {
            "r": int(block['r']),
            "g": int(block['g']),
            "b": int(block['b']),
            "pixelCount": int(count),
        }
        for block, count in zip(color_blocks, counts.tolist())
    ]
    source_colors = [
        (entry["r"], entry["g"], entry["b"])
        for entry in source_entries
    ]

    result_codes, result_rgbs = _map_source_colors_to_blends(
        source_colors=source_colors,
        colors=active_colors,
        layer_height=layer_height,
        layer_count=layer_count,
        backing_layers=white_backing_layers,
        backing_mode=backing_mode,
    )

    processed_image = _render_labels(labels, result_rgbs)

    mapped_block_colors = []
    for code, rgb in zip(result_codes, result_rgbs):
        mapped_block_colors.append({
            "code": code,
            "rgb": list(rgb),
            "hex": _rgb_to_hex(rgb),
        })

    return {
        "processedImage": processed_image,
        "mappedBlockColors": mapped_block_colors,
        "mappedBlendPalette": _build_mapped_blend_palette(
            entries=source_entries,
            result_codes=result_codes,
            result_rgbs=result_rgbs,
            total_pixels=total_pixels,
        ),
        "printStack": build_print_stack(
            layer_count=layer_count,
            layer_height=layer_height,
            backing_layers=white_backing_layers,
            backing_mode=backing_mode,
        ),
    }


def build_vector_simulated_preview(
    quantized_image: np.ndarray,
    vector_results: list[dict],
    pixel_size: float,
    detail_size: Optional[float],
    colors: Optional[Colors] = None,
    layer_count: int = 4,
    layer_height: float = 0.08,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
    ref_matrices: Optional[tuple] = None,  # Pre-computed (ref_code_matrix, ref_rgb_matrix)
) -> dict:
    """Build an image-specific print preview for SVG mode from vectorized regions."""
    active_colors = colors or Colors()
    from services.print_stack import (
        PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label,
    )
    b_label = resolve_backing_label(active_colors, white_backing_layers, backing_mode)
    b_suffix = backing_suffix(b_label, white_backing_layers)
    b_boundary = PRINT_BACKGROUND_RGB if b_suffix else None
    image_dimensions = {
        'width': int(quantized_image.shape[1]),
        'height': int(quantized_image.shape[0]),
    }

    from services.vector_processor import finalize_vector_partition
    partition = finalize_vector_partition(
        vector_results, image_dimensions, pixel_size, detail_size,
    )
    counts = np.bincount(partition.ravel(), minlength=len(vector_results))

    source_entries = [
        {
            "r": int(result['color'][0]),
            "g": int(result['color'][1]),
            "b": int(result['color'][2]),
            "pixelCount": int(counts[index]),
        }
        for index, result in enumerate(vector_results)
    ]
    source_colors = [
        (entry["r"], entry["g"], entry["b"])
        for entry in source_entries
    ]
    
    # Use pre-computed matrices if provided, otherwise compute them
    if ref_matrices is not None:
        ref_code_matrix, ref_rgb_matrix = ref_matrices
        result_codes, result_rgbs = _map_and_refine(
            source_colors, ref_code_matrix, ref_rgb_matrix,
            active_colors, layer_count, layer_height,
            backing_suffix=b_suffix, background_rgb=b_boundary,
        )
    else:
        result_codes, result_rgbs = _map_source_colors_to_blends(
            source_colors=source_colors,
            colors=active_colors,
            layer_count=layer_count,
            layer_height=layer_height,
            backing_layers=white_backing_layers,
            backing_mode=backing_mode,
        )
    
    simulated = np.asarray(result_rgbs, dtype=np.uint8)[partition]

    return {
        "processedImage": _image_to_data_url(Image.fromarray(simulated)),
        "mappedBlendPalette": _build_mapped_blend_palette(
            entries=source_entries,
            result_codes=result_codes,
            result_rgbs=result_rgbs,
            total_pixels=partition.size,
        ),
        "printStack": build_print_stack(
            layer_count=layer_count,
            layer_height=layer_height,
            backing_layers=white_backing_layers,
            backing_mode=backing_mode,
        ),
    }


def is_dark_neutral_color(
    color: tuple[int, int, int],
    neutral_threshold: int = 35,
    dark_threshold: int = 150
) -> bool:
    """
    Check if a color is dark and neutral (gray/black-ish)
    """
    dim = (color[0] + color[1] + color[2]) < dark_threshold
    max_val = max(color)
    min_val = min(color)
    neutral = (max_val - min_val) < neutral_threshold
    return dim and neutral


def cluster_avg_color(cluster: list[dict]) -> dict:
    """
    Calculate average color of a cluster
    """
    return {
        'r': int(round(sum(c['r'] for c in cluster) / len(cluster))),
        'g': int(round(sum(c['g'] for c in cluster) / len(cluster))),
        'b': int(round(sum(c['b'] for c in cluster) / len(cluster))),
        'count': sum(c['count'] for c in cluster),
        'pixels': [p for c in cluster for p in c['pixels']]
    }


def merge_similar_colors(colors: list[dict], threshold: float) -> list[dict]:
    """
    Merge colors that are similar within threshold.
    Distance is Euclidean in OpenCV's 8-bit Lab space (L scaled to 0-255),
    so the threshold is in those units rather than CIELAB ΔE.

    Uses a fast pre-quantization step to reduce the number of unique colors
    before the O(n²) greedy merge, keeping performance acceptable even for
    large natural photos with 200k+ unique RGB values. The pre-quantization
    is lossy (5-bit buckets); it engages only when the unique-color count
    makes the exact O(n²) merge unaffordable, so small exact-palette inputs
    (e.g. synthetic grids) keep full 8-bit fidelity.
    """
    if not colors:
        return colors

    # --- Exact path: small sets skip the lossy bucket pre-quantization ---
    if len(colors) <= EXACT_MERGE_MAX_UNIQUE:
        pre_merged: list[dict] = list(colors)
    else:
        # --- Fast pre-quantization: bin RGB into 32-level buckets (8 bits → 5 bits) ---
        # Colors that fall into the same bucket are merged immediately (weighted avg).
        # This reduces 200k+ unique colors to at most 32³ = 32768 buckets in O(n).
        QUANT_BITS = 3  # shift right by 3 → 32 levels per channel
        bucket: dict[tuple[int, int, int], list[dict]] = {}
        for c in colors:
            key = (c['r'] >> QUANT_BITS, c['g'] >> QUANT_BITS, c['b'] >> QUANT_BITS)
            bucket.setdefault(key, []).append(c)

        pre_merged = [cluster_avg_color(v) for v in bucket.values()]

    # --- OpenCV 8-bit Lab conversion in one batch (L scaled to 0-255; the
    # merge threshold is in these units, not CIELAB ΔE) ---
    rgb_array = np.array(
        [(c['r'], c['g'], c['b']) for c in pre_merged], dtype=np.uint8
    ).reshape(1, -1, 3)
    lab_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2Lab).reshape(-1, 3).astype(np.float32)

    n = len(pre_merged)
    is_dark = np.array([is_dark_neutral_color((c['r'], c['g'], c['b'])) for c in pre_merged])

    # --- Greedy merge on the reduced set ---
    used = np.zeros(n, dtype=bool)
    merged: list[dict] = []

    for idx in range(n):
        if used[idx]:
            continue
        used[idx] = True

        # Vectorised distance from idx to all remaining candidates
        diff = lab_array[idx] - lab_array  # (n, 3)
        dists = np.sqrt((diff * diff).sum(axis=1))  # (n,)

        if is_dark[idx]:
            mask = (~used) & is_dark & (dists < threshold)
        else:
            mask = (~used) & (dists < threshold)

        cluster_indices = np.where(mask)[0]
        used[cluster_indices] = True

        cluster = [pre_merged[idx]] + [pre_merged[i] for i in cluster_indices]
        merged.append(cluster_avg_color(cluster))

    return merged


def reassign_colors(main_colors: list[dict], rest_colors: list[dict]) -> list[dict]:
    """
    Reassign pixels from rest_colors to nearest main_color
    """
    for tbd_color in rest_colors:
        tbd_rgb = (tbd_color['r'], tbd_color['g'], tbd_color['b'])

        for pixel in tbd_color['pixels']:
            # Find nearest main color
            min_dist = float('inf')
            nearest_idx = 0

            for idx, main_color in enumerate(main_colors):
                main_rgb = (main_color['r'], main_color['g'], main_color['b'])
                dist = color_distance(tbd_rgb, main_rgb)
                if dist < min_dist:
                    min_dist = dist
                    nearest_idx = idx

            # Add pixel to nearest color
            main_colors[nearest_idx]['pixels'].append(pixel)
            main_colors[nearest_idx]['count'] += 1

    return main_colors


def model_pitch(width_px: int, height_px: int, pixel_size: float, detail_size: Optional[float]) -> float:
    """Model grid pitch in mm for a width_px x height_px image at pixel_size mm per pixel.

    Images within settings.max_model_cells cells and MAX_PROCESSING_DIMENSION
    cells per side keep their pixel grid; larger ones are resampled to fit.
    When resampling, a pitch between half and one detail width becomes one
    detail width: such cells add no printable resolution but make the
    printability cleanup slow.
    """
    pitch = max(
        pixel_size,
        pixel_size * math.sqrt(width_px * height_px / settings.max_model_cells),
        pixel_size * max(width_px, height_px) / MAX_PROCESSING_DIMENSION,
    )
    if detail_size and pitch > pixel_size and detail_size / 2 < pitch < detail_size:
        pitch = detail_size
    return pitch


def resample_to_model_grid(
    img: Image.Image, pixel_size: float, detail_size: Optional[float],
) -> tuple[Image.Image, float]:
    """Resample an image to its model grid; returns the image and its pitch in mm.

    Grid sides round down, so the pitch never falls below model_pitch and a
    grid that is already at its pitch passes through unchanged.
    """
    pitch = model_pitch(img.width, img.height, pixel_size, detail_size)
    if pitch <= pixel_size:
        return img, pixel_size
    scale = pixel_size / pitch
    size = (max(1, math.floor(img.width * scale)), max(1, math.floor(img.height * scale)))
    # The longest side keeps its physical length.
    actual_pitch = pixel_size * max(img.width, img.height) / max(size)
    logger.info(
        "Resampling image from %dx%d to %dx%d (%.3f -> %.3f mm cells)",
        img.width, img.height, size[0], size[1], pixel_size, actual_pitch,
    )
    return img.resize(size, Image.LANCZOS), actual_pitch


def merge_small_pixels_to_neighbors(
    color_blocks: list[dict],
    labels: np.ndarray,
    pixel_size: float,
    detail_size: float,
) -> tuple[list[dict], np.ndarray]:
    """
    Make every color region printable at detail_size without rescaling the model.

    Sub-detail strokes are widened and sub-detail noise joins a neighboring
    color (see ``regularize_printable_regions``).

    Args:
        color_blocks: Color blocks; block i covers the cells where labels == i
        labels: (height, width) label map of the model grid
        pixel_size: Physical size of each pixel in mm
        detail_size: Minimum physical pixel size in mm

    Returns:
        The remaining blocks, largest first, and their label map
    """
    if pixel_size >= detail_size:
        return color_blocks, labels

    cleaned = regularize_printable_regions(
        labels=labels.astype(np.int32),
        colors=[(int(block['r']), int(block['g']), int(block['b'])) for block in color_blocks],
        pixel_size=pixel_size,
        detail_size=detail_size,
    )
    counts = block_cell_counts(cleaned, len(color_blocks))
    return _keep_blocks(color_blocks, cleaned, [
        i for i in np.argsort(-counts, kind='stable').tolist() if counts[i] > 0
    ])


def _keep_blocks(color_blocks: list[dict], labels: np.ndarray, order: list[int]) -> tuple[list[dict], np.ndarray]:
    """The blocks at `order`, relabelled 0..len(order)-1 in that order."""
    remap = np.full(len(color_blocks), EMPTY, dtype=np.uint8)
    remap[order] = np.arange(len(order), dtype=np.uint8)
    return [color_blocks[i] for i in order], remap[labels]


def process_image(
    image_bytes: bytes,
    max_colors: int = 10,
    color_threshold: float = 50,
    pixel_size: float = 0.08,
    filament_colors: Optional[Colors] = None,
    layer_count: int = 4,
    layer_height: float = 0.08,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
    detail_size: Optional[float] = None,
) -> dict:
    """
    Process uploaded image to extract color blocks

    Args:
        image_bytes: Raw image bytes
        max_colors: Maximum number of colors to extract
        color_threshold: Threshold for merging similar colors
        pixel_size: Physical size of each pixel in mm
        detail_size: Minimum physical pixel size in mm

    Returns:
        Dictionary containing colorBlocks, processedImage, segmentationImage,
        mappedBlendPalette, and imageDimensions
    """
    # Load and optionally downscale image
    img = Image.open(BytesIO(image_bytes))
    # Convert RGBA to RGB with white background for 3D printing
    # (transparent = no filament = white base color)
    if img.mode == 'RGBA':
        # Create white background
        background = Image.new('RGB', img.size, (255, 255, 255))
        # Paste RGBA image onto white background using alpha channel as mask
        background.paste(img, mask=img.split()[3])  # alpha channel
        img = background
    else:
        img = img.convert('RGB')

    img, pixel_size = resample_to_model_grid(img, pixel_size, detail_size)
    width, height = img.size

    # Convert to numpy array
    img_array = np.array(img)
    pixels = img_array.reshape(-1, 3)

    # Vectorized unique-color extraction: encode each RGB triple as a single int32
    # to use numpy's unique() instead of a Python dict loop.
    packed = (pixels[:, 0].astype(np.int32) << 16
              | pixels[:, 1].astype(np.int32) << 8
              | pixels[:, 2].astype(np.int32))
    unique_packed, inverse = np.unique(packed, return_inverse=True)
    counts = np.bincount(inverse)

    # Build lightweight color_blocks (count only, no pixel lists yet).
    # Pixel lists are expensive to build for 200k+ unique colors and are only
    # needed after we've reduced to the final small set of colors.
    color_blocks = [
        {
            'r': int((p >> 16) & 0xFF),
            'g': int((p >> 8) & 0xFF),
            'b': int(p & 0xFF),
            'count': int(counts[idx]),
            'pixels': [],  # populated later after color reduction
        }
        for idx, p in enumerate(unique_packed)
    ]

    # Step 1: Merge similar colors
    color_blocks = merge_similar_colors(color_blocks, color_threshold)

    # Step 2: Sort by frequency
    color_blocks.sort(key=lambda c: c['count'], reverse=True)

    main_colors = color_blocks[:max_colors]
    rest_colors = color_blocks[max_colors:]

    # Step 4: Reassign remaining colors to nearest main color (count-only, no pixels yet)
    if rest_colors:
        # Vectorized reassignment: for each rest color find nearest main color by RGB distance
        main_rgb = np.array([[c['r'], c['g'], c['b']] for c in main_colors], dtype=np.float32)
        for tbd in rest_colors:
            tbd_rgb = np.array([tbd['r'], tbd['g'], tbd['b']], dtype=np.float32)
            dists = np.sum((main_rgb - tbd_rgb) ** 2, axis=1)
            nearest = int(np.argmin(dists))
            main_colors[nearest]['count'] += tbd['count']
        color_blocks = main_colors
    else:
        color_blocks = main_colors

    # Step 4b: Build a mapping from every unique packed color → final color index,
    # then populate pixel lists in one pass over all pixels.
    # For each unique color, find the nearest final color by RGB distance.
    final_rgb = np.array([[c['r'], c['g'], c['b']] for c in color_blocks], dtype=np.float32)
    unique_rgb = np.array(
        [((p >> 16) & 0xFF, (p >> 8) & 0xFF, p & 0xFF) for p in unique_packed],
        dtype=np.float32,
    )
    # Batch nearest-neighbor: (n_unique, 3) vs (n_final, 3). A resampled photo
    # has up to ~1M unique colors, so broadcast in slices to bound memory.
    unique_to_final = np.empty(len(unique_rgb), dtype=np.intp)  # index into color_blocks
    for start in range(0, len(unique_rgb), NEAREST_FINAL_CHUNK):
        diffs = unique_rgb[start:start + NEAREST_FINAL_CHUNK, np.newaxis, :] - final_rgb[np.newaxis, :, :]
        unique_to_final[start:start + NEAREST_FINAL_CHUNK] = (diffs * diffs).sum(axis=2).argmin(axis=1)

    # Label map: each cell's final color index (services/label_map.py).
    labels = unique_to_final[inverse].reshape(height, width).astype(np.uint8)

    # Step 5: Merge small pixel clusters if detail_size is specified
    if detail_size is not None and detail_size > pixel_size:
        color_blocks, labels = merge_small_pixels_to_neighbors(color_blocks, labels, pixel_size, detail_size)
    else:
        counts = block_cell_counts(labels, len(color_blocks))
        color_blocks, labels = _keep_blocks(color_blocks, labels, [i for i in range(len(color_blocks)) if counts[i] > 0])

    # Counts, pixel lists (for the response) and hex values
    counts = block_cell_counts(labels, len(color_blocks))
    for color, count, block_cells in zip(color_blocks, counts.tolist(), block_pixels(labels, len(color_blocks))):
        color['count'] = count
        color['pixels'] = block_cells
        color['hex'] = f"#{color['r']:02x}{color['g']:02x}{color['b']:02x}"

    segmentation_image = _render_labels(
        labels, [(int(color['r']), int(color['g']), int(color['b'])) for color in color_blocks],
    )
    simulated_preview = build_simulated_print_preview(
        color_blocks=color_blocks,
        labels=labels,
        colors=filament_colors,
        layer_count=layer_count,
        layer_height=layer_height,
        white_backing_layers=white_backing_layers,
        backing_mode=backing_mode,
    )

    return {
        'colorBlocks': color_blocks,
        'labels': labels,
        'processedImage': simulated_preview['processedImage'],
        'segmentationImage': segmentation_image,
        'mappedBlockColors': simulated_preview['mappedBlockColors'],
        'mappedBlendPalette': simulated_preview['mappedBlendPalette'],
        'imageDimensions': {
            'width': width,
            'height': height
        },
        'pixelSize': pixel_size,
        'printStack': simulated_preview['printStack'],
    }
