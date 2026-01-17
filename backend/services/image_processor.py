"""
Image processing service for color extraction and clustering
"""
import base64
from io import BytesIO

import numpy as np
from PIL import Image


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

        # Handle dark neutral colors separately
        if is_dark_neutral_color(color_rgb):
            dark.append(color)

            for i in range(idx + 1, len(colors)):
                if i in used:
                    continue

                other_color = colors[i]
                other_rgb = (other_color['r'], other_color['g'], other_color['b'])

                if is_dark_neutral_color(other_rgb):
                    dark.append(other_color)
                    used.add(i)

            # Calculate average color for dark cluster
            avg = cluster_avg_color(dark)
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
    # Load image
    img = Image.open(BytesIO(image_bytes))
    img = img.convert('RGB')

    width, height = img.size

    # Convert to numpy array
    img_array = np.array(img)
    pixels = img_array.reshape(-1, 3)

    # Extract unique colors with pixel positions
    color_map = {}

    for i in range(len(pixels)):
        r, g, b = pixels[i]
        key = f"{r},{g},{b}"
        x = i % width
        y = i // width

        if key not in color_map:
            color_map[key] = {
                'r': int(r),
                'g': int(g),
                'b': int(b),
                'count': 0,
                'pixels': []
            }

        color_map[key]['count'] += 1
        color_map[key]['pixels'].append({'x': int(x), 'y': int(y)})

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

    # Generate processed image preview
    processed_img_array = np.zeros((height, width, 3), dtype=np.uint8)
    pixel_color_map = {}

    for color in colors:
        for pixel in color['pixels']:
            key = f"{pixel['x']},{pixel['y']}"
            pixel_color_map[key] = color

    for y in range(height):
        for x in range(width):
            key = f"{x},{y}"
            if key in pixel_color_map:
                color = pixel_color_map[key]
                processed_img_array[y, x] = [color['r'], color['g'], color['b']]

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
