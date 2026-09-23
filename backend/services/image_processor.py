"""
Image processing service for color extraction and clustering
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import base64
import logging
from io import BytesIO
from typing import Callable, Optional

import numpy as np
import cv2
from PIL import Image

from core.blend_color import Colors
from core.color_materials import Color
from services.print_stack import build_print_stack, resolve_backing_label
from services.raster_cleanup import color_distance, regularize_printable_regions
from services.stl_generator import compute_reference_matrices
from services.vector_processor import render_vector_results_image

logger = logging.getLogger(__name__)

# Safety cap only — prevents truly pathological inputs (e.g. 100MP raw photos).
# Normal photos are processed at full resolution; pixelSize controls physical output size.
MAX_PROCESSING_DIMENSION = 4096
# Unique-color count at or below which merge_similar_colors runs the exact
# O(n²) path without the lossy 5-bit bucket pre-quantization. Above it
# (natural-photo scale) the pre-quantization engages to bound the merge cost.
EXACT_MERGE_MAX_UNIQUE = 4096


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _image_to_data_url(img: Image.Image) -> str:
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


def _render_color_block_image(
    color_blocks: list[dict],
    width: int,
    height: int,
    rgb_getter: Callable[[dict, int], tuple[int, int, int]],
) -> str:
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    for idx, color in enumerate(color_blocks):
        rgb = np.array(rgb_getter(color, idx), dtype=np.uint8)
        for pixel in color['pixels']:
            img_array[pixel['y'], pixel['x']] = rgb
    return _image_to_data_url(Image.fromarray(img_array))


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
    return [code + backing_suffix for code in result_codes], normalized_rgbs


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
    image_dimensions: dict,
    colors: Optional[Colors] = None,
    layer_count: int = 4,
    layer_height: float = 0.08,
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_mode: str = 'white',
) -> dict:
    """
    Build an image-specific print preview from current color blocks.

    The preview uses the same nearest printable blend mapping as STL export.
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    active_colors = colors or Colors()
    resolve_backing_label(active_colors, white_backing_layers, backing_mode)
    width = image_dimensions['width']
    height = image_dimensions['height']
    total_pixels = max(1, sum(block.get('count', len(block['pixels'])) for block in color_blocks))

    source_entries = [
        {
            "r": int(block['r']),
            "g": int(block['g']),
            "b": int(block['b']),
            "pixelCount": int(block.get('count', len(block['pixels']))),
        }
        for block in color_blocks
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

    processed_image = _render_color_block_image(
        color_blocks,
        width,
        height,
        lambda _block, idx: result_rgbs[idx],
    )

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
    Distance is computed in CIELAB space for perceptual accuracy.

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

    # --- CIELAB conversion in one batch ---
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


def _downscale_if_needed(img: Image.Image, max_dim: int) -> Image.Image:
    """
    Downscale image if either dimension exceeds max_dim, preserving aspect ratio.

    Args:
        img: PIL Image
        max_dim: Maximum allowed dimension

    Returns:
        Original or downscaled PIL Image
    """
    width, height = img.size
    if width <= max_dim and height <= max_dim:
        return img

    scale = max_dim / max(width, height)
    new_width = int(width * scale)
    new_height = int(height * scale)
    # Clamp to minimum 1 pixel to prevent zero-dimension images
    new_width = max(1, new_width)
    new_height = max(1, new_height)
    logger.info(
        "Downscaling image from %dx%d to %dx%d for processing",
        width, height, new_width, new_height
    )
    return img.resize((new_width, new_height), Image.LANCZOS)


def merge_small_pixels_to_neighbors(
    color_blocks: list[dict],
    width: int,
    height: int,
    pixel_size: float,
    detail_size: float,
) -> list[dict]:
    """
    Merge pixels smaller than detail_size with their nearest color-similar neighbor.
    
    This prevents tiny details from being printed at sub-detail-size scale,
    without forcing the entire model to be scaled up.
    
    Args:
        color_blocks: List of color blocks with pixels
        width: Image width in pixels
        height: Image height in pixels
        pixel_size: Physical size of each pixel in mm
        detail_size: Minimum physical pixel size in mm
    
    Returns:
        Updated color_blocks with small regions merged
    """
    if pixel_size >= detail_size:
        return color_blocks

    label_grid = np.zeros((height, width), dtype=np.int32)
    palette = [
        (int(block['r']), int(block['g']), int(block['b']))
        for block in color_blocks
    ]
    for idx, block in enumerate(color_blocks):
        for pixel in block['pixels']:
            label_grid[pixel['y'], pixel['x']] = idx

    cleaned_labels = regularize_printable_regions(
        labels=label_grid,
        colors=palette,
        pixel_size=pixel_size,
        detail_size=detail_size,
    )

    rebuilt_blocks = {}
    for y in range(height):
        for x in range(width):
            idx = int(cleaned_labels[y, x])
            if idx not in rebuilt_blocks:
                r, g, b = palette[idx]
                rebuilt_blocks[idx] = {
                    'r': r,
                    'g': g,
                    'b': b,
                    'hex': color_blocks[idx].get('hex', f"#{r:02x}{g:02x}{b:02x}"),
                    'count': 0,
                    'pixels': [],
                }
            rebuilt_blocks[idx]['pixels'].append({'x': x, 'y': y})
            rebuilt_blocks[idx]['count'] += 1

    result = list(rebuilt_blocks.values())
    result.sort(key=lambda c: c['count'], reverse=True)
    return result


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
    target_width: Optional[float] = None,
    detail_size: Optional[float] = None,
) -> dict:
    """
    Process uploaded image to extract color blocks

    Args:
        image_bytes: Raw image bytes
        max_colors: Maximum number of colors to extract
        color_threshold: Threshold for merging similar colors
        pixel_size: Physical size of each pixel in mm
        target_width: Explicit physical target width in mm (deprecated, not used)
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

    # Standard safety downscale only
    img = _downscale_if_needed(img, MAX_PROCESSING_DIMENSION)

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
    # Batch nearest-neighbor: (n_unique, 3) vs (n_final, 3)
    # Use broadcasting; n_unique up to ~32k after pre-quant, n_final <= max_colors
    diffs = unique_rgb[:, np.newaxis, :] - final_rgb[np.newaxis, :, :]  # (U, F, 3)
    sq_dists = (diffs * diffs).sum(axis=2)  # (U, F)
    unique_to_final = sq_dists.argmin(axis=1)  # (U,) index into color_blocks

    # Map each pixel to its final color index via the inverse array
    pixel_to_final = unique_to_final[inverse]  # (total_pixels,)

    # Populate pixel lists and build a label map for fast rendering.
    total_pixels = len(pixels)
    xs = np.arange(total_pixels, dtype=np.int32) % width
    ys = np.arange(total_pixels, dtype=np.int32) // width

    # label_map[y, x] = final color index — used for fast image rendering
    label_map = pixel_to_final.reshape(height, width)

    # Build pixel lists grouped by color index (needed by downstream consumers)
    sort_idx = np.argsort(pixel_to_final, kind='stable')
    sorted_ci = pixel_to_final[sort_idx]
    sorted_xs = xs[sort_idx]
    sorted_ys = ys[sort_idx]
    boundaries = np.searchsorted(sorted_ci, np.arange(len(color_blocks) + 1))
    for ci in range(len(color_blocks)):
        lo, hi = int(boundaries[ci]), int(boundaries[ci + 1])
        gxs = sorted_xs[lo:hi].tolist()
        gys = sorted_ys[lo:hi].tolist()
        color_blocks[ci]['pixels'] = [{'x': x, 'y': y} for x, y in zip(gxs, gys)]
        color_blocks[ci]['count'] = hi - lo
    
    # Step 5: Merge small pixel clusters if detail_size is specified
    if detail_size is not None and detail_size > pixel_size:
        color_blocks = merge_small_pixels_to_neighbors(
            color_blocks, width, height, pixel_size, detail_size
        )

    # Add hex values
    for color in color_blocks:
        color['hex'] = f"#{color['r']:02x}{color['g']:02x}{color['b']:02x}"

    segmentation_image = _render_color_block_image(
        color_blocks,
        width,
        height,
        lambda color, _idx: (int(color['r']), int(color['g']), int(color['b'])),
    )
    simulated_preview = build_simulated_print_preview(
        color_blocks=color_blocks,
        image_dimensions={"width": width, "height": height},
        colors=filament_colors,
        layer_count=layer_count,
        layer_height=layer_height,
        white_backing_layers=white_backing_layers,
        backing_mode=backing_mode,
    )

    return {
        'colorBlocks': color_blocks,
        'processedImage': simulated_preview['processedImage'],
        'segmentationImage': segmentation_image,
        'mappedBlockColors': simulated_preview['mappedBlockColors'],
        'mappedBlendPalette': simulated_preview['mappedBlendPalette'],
        'imageDimensions': {
            'width': width,
            'height': height
        },
        'printStack': simulated_preview['printStack'],
    }
