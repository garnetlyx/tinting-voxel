"""Printed backing layers share the same illumination as the color stack."""
from config.print_defaults import DEFAULT_BACKING_LAYERS
from typing import Optional

import numpy as np

from core.blend_color import Colors
from core.color_materials import Color

PRINT_BACKGROUND_RGB = (255.0, 255.0, 255.0)


def normalize_backing_layers(backing_layers: Optional[int]) -> int:
    """Normalize optional backing configuration to a concrete non-negative count."""
    if backing_layers is None:
        return DEFAULT_BACKING_LAYERS
    return max(0, int(backing_layers))


def default_backing_label(colors: Colors) -> str:
    """The filament that looks closest to white (CIEDE2000).

    The backing reflects light back through the color layers, so a light
    neutral keeps colors true. RGB distance would rank a bright yellow closer
    to white than a neutral grey.
    """
    labels = colors.get_labels()
    if not labels:
        raise ValueError("Colors instance has no colors defined")
    filament_lab = np.array([Color.get_lab(colors[label].rgb)[:3] for label in labels])
    white_lab = np.array(Color.get_lab((255, 255, 255))[:3])
    return labels[int(np.argmin(Color.perceptual_distance_raw(white_lab, filament_lab)))]


def resolve_backing_label(
    colors: Colors,
    backing_layers: Optional[int],
    backing_filament: Optional[str] = None,
) -> Optional[str]:
    """The label of the filament printed as the backing block (None without one).

    backing_filament names one of the set's filaments by label; when omitted
    the set's default_backing_label applies.
    """
    if normalize_backing_layers(backing_layers) <= 0:
        return None
    if backing_filament is None:
        return default_backing_label(colors)
    labels = colors.get_labels()
    if backing_filament not in labels:
        raise ValueError(
            f"Backing filament '{backing_filament}' is not in this filament set ({', '.join(labels)})."
        )
    return backing_filament


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
    backing_label: Optional[str] = None,
) -> dict:
    """Build shared stack metadata for UI, exports, and print settings."""
    backing = normalize_backing_layers(backing_layers)
    total_layer_count = layer_count + backing
    return {
        "opticalLayerCount": layer_count,
        "whiteBackingLayers": backing,
        "backingFilament": backing_label if backing else None,
        "totalLayerCount": total_layer_count,
        "totalHeightMm": total_layer_count * layer_height,
    }
