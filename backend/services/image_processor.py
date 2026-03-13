"""
Image processing service for color extraction and clustering
"""
import base64
import logging
from io import BytesIO
from typing import Callable, Optional

import numpy as np
from PIL import Image

from core.blend_color import Colors
from core.color_materials import Color
from services.print_stack import build_print_stack, resolve_white_backing_label
from services.raster_cleanup import color_distance, merge_small_label_regions
from services.stl_generator import compute_reference_matrices
from services.vector_processor import render_vector_results_image

logger = logging.getLogger(__name__)

# Maximum dimension before auto-downscaling (preserves aspect ratio)
MAX_PROCESSING_DIMENSION = 1024


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


def _map_source_colors_to_blends(
    source_colors: list[tuple[int, int, int]],
    colors: Colors,
    layer_count: int,
    layer_height: float,
) -> tuple[list[str], list[tuple[int, int, int]]]:
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count,
        layer_height,
        colors,
    )
    result_codes, result_rgbs = Color.map_to_nearest_color(
        source_colors,
        ref_code_matrix,
        ref_rgb_matrix,
    )
    normalized_rgbs = [
        tuple(int(channel) for channel in np.asarray(rgb).tolist())
        for rgb in result_rgbs
    ]
    return result_codes, normalized_rgbs


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
    white_backing_layers: int = 1,
) -> dict:
    """
    Build an image-specific print preview from current color blocks.

    The preview uses the same nearest printable blend mapping as STL export.
    """
    if not color_blocks:
        raise ValueError("No color blocks provided")

    active_colors = colors or Colors()
    resolve_white_backing_label(active_colors, white_backing_layers)
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
            white_backing_layers=white_backing_layers,
        ),
    }


def build_vector_simulated_preview(
    quantized_image: np.ndarray,
    vector_results: list[dict],
    colors: Optional[Colors] = None,
    layer_count: int = 4,
    layer_height: float = 0.08,
    white_backing_layers: int = 1,
) -> dict:
    """Build an image-specific print preview for SVG mode from vectorized regions."""
    active_colors = colors or Colors()
    resolve_white_backing_label(active_colors, white_backing_layers)
    image_dimensions = {
        'width': int(quantized_image.shape[1]),
        'height': int(quantized_image.shape[0]),
    }

    if not vector_results:
        return {
            "processedImage": _image_to_data_url(Image.fromarray(quantized_image)),
            "mappedBlendPalette": [],
            "printStack": build_print_stack(
                layer_count=layer_count,
                layer_height=layer_height,
                white_backing_layers=white_backing_layers,
            ),
        }

    source_entries = [
        {
            "r": int(result['color'][0]),
            "g": int(result['color'][1]),
            "b": int(result['color'][2]),
            "pixelCount": int(result['pixel_count']),
        }
        for result in vector_results
    ]
    source_colors = [
        (entry["r"], entry["g"], entry["b"])
        for entry in source_entries
    ]
    result_codes, result_rgbs = _map_source_colors_to_blends(
        source_colors=source_colors,
        colors=active_colors,
        layer_count=layer_count,
        layer_height=layer_height,
    )
    
    # Use quantized image as background to avoid white edges from filtered regions
    # Map all quantized colors (not just vector results) to their blend equivalents
    unique_colors_in_quantized = []
    for y in range(quantized_image.shape[0]):
        for x in range(quantized_image.shape[1]):
            color = tuple(quantized_image[y, x])
            if color not in unique_colors_in_quantized:
                unique_colors_in_quantized.append(color)
    
    all_codes, all_rgbs = _map_source_colors_to_blends(
        source_colors=unique_colors_in_quantized,
        colors=active_colors,
        layer_count=layer_count,
        layer_height=layer_height,
    )
    
    # Build color mapping dict
    color_map = {
        unique_colors_in_quantized[i]: all_rgbs[i]
        for i in range(len(unique_colors_in_quantized))
    }
    
    # Create background image with mapped colors
    background_image = np.zeros_like(quantized_image)
    for y in range(quantized_image.shape[0]):
        for x in range(quantized_image.shape[1]):
            color = tuple(quantized_image[y, x])
            background_image[y, x] = color_map.get(color, color)
    
    # Render vector results on top of the background
    simulated = background_image.copy()
    for idx, result in enumerate(vector_results):
        from services.vector_processor import normalize_regions, render_region_mask
        regions = normalize_regions(result)
        region_mask = render_region_mask(
            regions,
            width=image_dimensions['width'],
            height=image_dimensions['height'],
        )
        if region_mask.any():
            simulated[region_mask] = result_rgbs[idx]

    return {
        "processedImage": _image_to_data_url(Image.fromarray(simulated)),
        "mappedBlendPalette": _build_mapped_blend_palette(
            entries=source_entries,
            result_codes=result_codes,
            result_rgbs=result_rgbs,
            total_pixels=max(1, sum(entry["pixelCount"] for entry in source_entries)),
        ),
        "printStack": build_print_stack(
            layer_count=layer_count,
            layer_height=layer_height,
            white_backing_layers=white_backing_layers,
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
    Merge colors that are similar within threshold
    """
    merged = []
    used = set()
    dark = []

    for idx, color in enumerate(colors):
        if idx in used:
            continue
        used.add(idx)

        color_rgb = (color['r'], color['g'], color['b'])

        # Handle dark neutral colors with threshold check (same as non-dark)
        if is_dark_neutral_color(color_rgb):
            dark_cluster = [color]

            for i in range(idx + 1, len(colors)):
                if i in used:
                    continue

                other_color = colors[i]
                other_rgb = (other_color['r'], other_color['g'], other_color['b'])

                if is_dark_neutral_color(other_rgb) and color_distance(color_rgb, other_rgb) < threshold:
                    dark_cluster.append(other_color)
                    used.add(i)

            avg = cluster_avg_color(dark_cluster)
            merged.append(avg)
        else:
            cluster = [color]

            for i in range(idx + 1, len(colors)):
                if i in used:
                    continue

                other_color = colors[i]
                other_rgb = (other_color['r'], other_color['g'], other_color['b'])

                if color_distance(color_rgb, other_rgb) < threshold:
                    cluster.append(other_color)
                    used.add(i)

            # Calculate average color for cluster
            avg = cluster_avg_color(cluster)
            merged.append(avg)

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

    # First remove thin features
    from services.raster_cleanup import remove_thin_features
    filtered_labels = remove_thin_features(
        labels=label_grid,
        colors=palette,
        pixel_size=pixel_size,
        detail_size=detail_size,
    )

    # Then merge small regions
    cleaned_labels = merge_small_label_regions(
        labels=filtered_labels,
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
    white_backing_layers: int = 1,
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

    # Build coordinate arrays once (avoids repeated divmod in loop)
    total_pixels = len(pixels)
    xs = np.arange(total_pixels) % width
    ys = np.arange(total_pixels) // width

    # Extract unique colors with pixel positions using integer tuple keys
    color_map = {}

    for i in range(total_pixels):
        r, g, b = int(pixels[i, 0]), int(pixels[i, 1]), int(pixels[i, 2])
        key = (r, g, b)

        if key not in color_map:
            color_map[key] = {
                'r': r,
                'g': g,
                'b': b,
                'count': 0,
                'pixels': []
            }

        color_map[key]['count'] += 1
        color_map[key]['pixels'].append({'x': int(xs[i]), 'y': int(ys[i])})

    # Convert to list
    color_blocks = list(color_map.values())

    # Step 1: Merge similar colors
    color_blocks = merge_similar_colors(color_blocks, color_threshold)

    # Step 2: Sort by frequency
    color_blocks.sort(key=lambda c: c['count'], reverse=True)

    # Step 3: Limit to max colors
    main_colors = color_blocks[:max_colors]
    rest_colors = color_blocks[max_colors:]

    # Step 4: Reassign remaining colors to nearest main color
    if rest_colors:
        color_blocks = reassign_colors(main_colors, rest_colors)
    else:
        color_blocks = main_colors
    
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
