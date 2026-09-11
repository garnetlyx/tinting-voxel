"""
Shared print stack helpers for optical layers, white backing, and total height.
"""
from typing import Optional

from core.blend_color import Colors


def normalize_white_backing_layers(white_backing_layers: Optional[int]) -> int:
    """Normalize optional backing configuration to a concrete non-negative count."""
    if white_backing_layers is None:
        return 1
    return max(0, int(white_backing_layers))


def resolve_white_backing_label(colors: Colors, white_backing_layers: int) -> Optional[str]:
    """
    Resolve the white filament label for backing generation.

    Raises:
        ValueError: If backing is requested but the filament config has no white filament.
    """
    if white_backing_layers <= 0:
        return None

    labels = colors.get_labels()
    if 'W' in labels:
        return 'W'
    for label in labels:
        if colors[label].hex.upper() == '#FFFFFF':
            return label

    raise ValueError(
        "whiteBackingLayers requires a white filament in the active filament configuration"
    )


def build_print_stack(
    layer_count: int,
    layer_height: float,
    white_backing_layers: Optional[int] = None,
    double_sided: bool = False,
) -> dict:
    """Build shared stack metadata for UI, exports, and print settings."""
    backing_layers = normalize_white_backing_layers(white_backing_layers)
    optical_layer_count = layer_count * (2 if double_sided else 1)
    total_layer_count = optical_layer_count + backing_layers
    total_height_mm = round(total_layer_count * layer_height, 2)

    return {
        "opticalLayerCount": optical_layer_count,
        "whiteBackingLayers": backing_layers,
        "totalLayerCount": total_layer_count,
        "totalHeightMm": total_height_mm,
    }
