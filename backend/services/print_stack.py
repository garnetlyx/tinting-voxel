"""Printed backing layers share the same illumination as the color stack."""
from config.print_defaults import DEFAULT_BACKING_LAYERS
from typing import Optional

from core.blend_color import Colors

BACKING_MODES = ('white', 'black')

PRINT_BACKGROUND_RGB = (255.0, 255.0, 255.0)

_BACKING_TARGET_RGB = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}


def normalize_backing_layers(backing_layers: Optional[int]) -> int:
    """Normalize optional backing configuration to a concrete non-negative count."""
    if backing_layers is None:
        return DEFAULT_BACKING_LAYERS
    return max(0, int(backing_layers))


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def resolve_backing_label(
    colors: Colors,
    backing_layers: Optional[int],
    backing_mode: str = 'white',
) -> Optional[str]:
    """
    Resolve the backing-block filament label for the requested mode.

    The backing filament is the one CLOSEST to the mode's pole (pure white /
    pure black) — a set without an exact #FFFFFF or near-black filament still
    resolves instead of erroring.
    """
    if backing_mode not in BACKING_MODES:
        raise ValueError(f"backing_mode must be one of {BACKING_MODES}, got {backing_mode!r}")
    if normalize_backing_layers(backing_layers) <= 0:
        return None

    labels = colors.get_labels()
    if not labels:
        raise ValueError("Colors instance has no colors defined")
    target = _BACKING_TARGET_RGB[backing_mode]
    return min(
        labels,
        key=lambda label: sum(
            (a - b) ** 2 for a, b in zip(_hex_to_rgb(colors[label].hex), target)
        ),
    )


def backing_suffix(backing_label: Optional[str], backing_layers: Optional[int]) -> str:
    """Backing block as trailing code layers (deepest in the light path)."""
    n = normalize_backing_layers(backing_layers)
    if backing_label is None or n <= 0:
        return ''
    return backing_label * n


def strip_backing_suffix(code: str, backing_label: Optional[str], backing_layers: Optional[int]) -> str:
    """Remove the appended backing suffix; exactly the last n chars are ours."""
    n = normalize_backing_layers(backing_layers)
    if backing_label is None or n <= 0 or len(code) <= n:
        return code
    return code[:-n]


def build_print_stack(
    layer_count: int,
    layer_height: float,
    backing_layers: Optional[int] = None,
    backing_mode: str = 'white',
) -> dict:
    """Build shared stack metadata for UI, exports, and print settings."""
    backing = normalize_backing_layers(backing_layers)
    total_layer_count = layer_count + backing
    return {
        "opticalLayerCount": layer_count,
        "whiteBackingLayers": backing,
        "backingMode": backing_mode,
        "totalLayerCount": total_layer_count,
        "totalHeightMm": total_layer_count * layer_height,
    }
