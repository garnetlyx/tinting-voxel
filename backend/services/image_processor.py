"""
Image processing service for color extraction and clustering
"""
import base64
import logging
from io import BytesIO

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Maximum dimension before auto-downscaling (preserves aspect ratio)
MAX_PROCESSING_DIMENSION = 1024


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """
    Calculate Euclidean distance between two RGB colors
    """
    return np.sqrt(
        (c1[0] - c2[0]) ** 2 +
        (c1[1] - c2[1]) ** 2 +
        (c1[2] - c2[2]) ** 2
    )


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


def process_image(
    image_bytes: bytes,
    max_colors: int = 10,
    color_threshold: float = 50,
    pixel_size: float = 0.08
) -> dict:
    """
    Process uploaded image to extract color blocks

    Args:
        image_bytes: Raw image bytes
        max_colors: Maximum number of colors to extract
        color_threshold: Threshold for merging similar colors
        pixel_size: Physical size of each pixel in mm

    Returns:
        Dictionary containing colorBlocks, processedImage, and imageDimensions
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
    colors = list(color_map.values())

    # Step 1: Merge similar colors
    colors = merge_similar_colors(colors, color_threshold)

    # Step 2: Sort by frequency
    colors.sort(key=lambda c: c['count'], reverse=True)

    # Step 3: Limit to max colors
    main_colors = colors[:max_colors]
    rest_colors = colors[max_colors:]

    # Step 4: Reassign remaining colors to nearest main color
    if rest_colors:
        colors = reassign_colors(main_colors, rest_colors)
    else:
        colors = main_colors

    # Add hex values
    for color in colors:
        color['hex'] = f"#{color['r']:02x}{color['g']:02x}{color['b']:02x}"

    # Generate processed image preview using numpy vectorized operations
    processed_img_array = np.zeros((height, width, 3), dtype=np.uint8)

    for color in colors:
        rgb = np.array([color['r'], color['g'], color['b']], dtype=np.uint8)
        for pixel in color['pixels']:
            processed_img_array[pixel['y'], pixel['x']] = rgb

    # Convert processed image to base64
    processed_img = Image.fromarray(processed_img_array)
    buffered = BytesIO()
    processed_img.save(buffered, format="PNG")
    processed_img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    processed_img_data_url = f"data:image/png;base64,{processed_img_base64}"

    return {
        'colorBlocks': colors,
        'processedImage': processed_img_data_url,
        'imageDimensions': {
            'width': width,
            'height': height
        }
    }
