"""
Print settings export service.

Generates slicer-compatible JSON configuration files containing
layer height, filament colors, object dimensions, and extruder assignments.
"""
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
    white_backing_layers: int = 1,
    base_plate_thickness: float = 0.0,
    filament_preset: Optional[str] = None,
    double_sided: bool = False,
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
        base_plate_thickness: Base plate thickness in mm
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
        white_backing_layers=white_backing_layers,
        base_plate_thickness=base_plate_thickness,
        double_sided=double_sided,
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

    settings = {
        "version": "1.0",
        "generator": "tinting-voxel",
        "print_settings": {
            "layer_height": layer_height,
            "layer_count": layer_count,
            "white_backing_layers": print_stack["whiteBackingLayers"],
            "base_plate_thickness": base_plate_thickness,
            "double_sided": double_sided,
        },
        "object_dimensions": {
            "width_mm": width_mm,
            "height_mm": height_mm,
            "total_height_mm": print_stack["totalHeightMm"],
            "total_layer_count": print_stack["totalLayerCount"],
            "optical_layer_count": print_stack["opticalLayerCount"],
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
