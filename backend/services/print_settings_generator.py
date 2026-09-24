"""
Print settings export service.

Generates slicer-compatible JSON configuration files containing
layer height, filament colors, object dimensions, and extruder assignments.
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import math
from config.print_defaults import TRANSPARENT_SLICER_LAYER_HEIGHT_MM
import json
import logging
from typing import Optional

from services.print_stack import build_print_stack

logger = logging.getLogger(__name__)


def generate_print_settings(
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    image_dimensions: dict,
    filament_colors: list[dict],
    white_backing_layers: int = DEFAULT_BACKING_LAYERS,
    backing_label: Optional[str] = None,
    filament_preset: Optional[str] = None,
) -> str:
    """
    Generate a JSON print settings file for slicer reference.

    Args:
        layer_height: Height of each layer in mm
        pixel_size: Physical size of each pixel in mm
        layer_count: Number of color layers
        image_dimensions: Dict with 'width' and 'height' keys (pixels)
        filament_colors: List of dicts with 'name', 'hex', 'transmission_distance'.
                         Must contain at least 1 color.
        backing_label: Label of the backing filament (resolve_backing_label)
        filament_preset: Name of the preset used (if any)

    Returns:
        JSON string with print settings

    Raises:
        ValueError: If filament_colors is empty or missing required keys.
    """
    if not filament_colors:
        raise ValueError(
            "filament_colors must contain at least 1 color, got empty list. "
            "Print settings require at least one extruder configuration."
        )

    try:
        width_mm = round(image_dimensions['width'] * pixel_size, 2)
        height_mm = round(image_dimensions['height'] * pixel_size, 2)
    except KeyError as e:
        raise ValueError(f"Missing required dimension key: {e}")

    print_stack = build_print_stack(
        layer_count=layer_count,
        layer_height=layer_height,
        backing_layers=white_backing_layers,
        backing_label=backing_label,
    )

    extruders = []
    for i, color in enumerate(filament_colors):
        try:
            extruders.append({
                "index": i,
                "name": color['name'],
                "color": color['hex'],
                "transmission_distance": color['transmission_distance'],
            })
        except KeyError as e:
            raise ValueError(f"Missing required filament color key: {e}")

    slices_per_color = max(1, math.ceil(layer_height / TRANSPARENT_SLICER_LAYER_HEIGHT_MM - 1e-9))
    slicer_layer_height = layer_height / slices_per_color
    settings = {
        "version": "1.0",
        "generator": "tinting-voxel",
        "print_settings": {
            "layer_height": slicer_layer_height,
            "color_layer_height_mm": layer_height,
            "slicer_layers_per_color_layer": slices_per_color,
            "color_layer_count": layer_count,
            "backing_color_layer_count": print_stack["whiteBackingLayers"],
            "backing_filament": next(
                (color['name'] for color in filament_colors if color['name'][0].upper() == print_stack["backingFilament"]),
                None,
            ),
        },
        "object_dimensions": {
            "width_mm": width_mm,
            "height_mm": height_mm,
            "total_height_mm": layer_height * print_stack["totalLayerCount"],
            "total_layer_count": slices_per_color * print_stack["totalLayerCount"],
            "optical_layer_count": slices_per_color * print_stack["opticalLayerCount"],
            "backing_layer_count": slices_per_color * print_stack["whiteBackingLayers"],
            "width_pixels": image_dimensions['width'],
            "height_pixels": image_dimensions['height'],
            "pixel_size_mm": pixel_size,
        },
        "filament": {
            "preset": filament_preset,
            "extruder_count": len(extruders),
            "extruders": extruders,
        },
    }

    result = json.dumps(settings, indent=2)

    logger.info(
        "Generated print settings: %d extruders, %.1fx%.1fmm, layer_height=%.2fmm",
        len(extruders), width_mm, height_mm, layer_height
    )

    return result
