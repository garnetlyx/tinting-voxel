"""
Shared print stack helpers: optical layers, printed backing block, total height.

The backing is a PRINTED block of N layers of one filament (white or black
mode) behind the optical stack. It participates in the color simulation as
real stack layers: the evaluated code carries the backing as a suffix and the
boundary behind the block uses the paper's backing reflectance (white paper
B=1; black cardstock B≈0.05). The paper's plates sat on infinite external
backings; here the backing is finite — its thickness (layer count) affects the
result.
"""
from typing import Optional

from core.blend_color import Colors

BACKING_MODES = ('white', 'black')

# Paper's black cardstock backing reflectance ≈ 0.05 per channel.
BLACK_BOUNDARY_RGB = (13.0, 13.0, 13.0)
WHITE_BOUNDARY_RGB = (255.0, 255.0, 255.0)

_BACKING_TARGET_RGB = {
    'white': (255, 255, 255),
    'black': (0, 0, 0),
}


def normalize_backing_layers(backing_layers: Optional[int]) -> int:
    """Normalize optional backing configuration to a concrete non-negative count."""
    if backing_layers is None:
        return 1
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


def backing_boundary_rgb(backing_mode: str) -> tuple[float, float, float]:
    """Boundary reflectance RGB behind the printed backing block (paper Eqs.)."""
    if backing_mode == 'black':
        return BLACK_BOUNDARY_RGB
    return WHITE_BOUNDARY_RGB


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
        "totalHeightMm": round(total_layer_count * layer_height, 2),
    }
