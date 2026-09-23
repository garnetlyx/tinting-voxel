"""
Reference matrix cache for color blend computations.

Caches the (code, rgb) reference matrices produced by
compute_reference_matrices, keyed by everything that determines their content:
the filament parameters (colors_key: label/TD channels/hex), layer count/height,
the printed backing, and whether the candidates are composition-pruned. The
target count only feeds the full-vs-pruned decision, so requests with different
color counts share one matrix. Content addressing means custom configurations
cache exactly like named presets — no preset-name special casing.

The cache is a small LRU: entries are pandas DataFrames whose size grows
with the candidate count, so only the most recent configurations are
retained.
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import logging
from collections import OrderedDict
from typing import Optional

import pandas as pd

from core.blend_color import Colors, colors_key
from core import color_config as _color_config

logger = logging.getLogger(__name__)

# Cache key: (color_key, layer_count, layer_height, pruned, backing).
_MATRIX_CACHE: OrderedDict[tuple, tuple[pd.DataFrame, pd.DataFrame]] = OrderedDict()
_MAX_ENTRIES = 8


def _default_backing_key_parts(colors: Colors) -> tuple[str, Optional[tuple]]:
    """Key parts for the DEFAULT backing configuration (three white layers) —
    what compute_reference_matrices resolves for backing_layers=None and
    what warmup stores. Explicit callers pass their own parts."""
    from services.print_stack import PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label

    label = resolve_backing_label(colors, DEFAULT_BACKING_LAYERS, 'white')
    suffix = backing_suffix(label, DEFAULT_BACKING_LAYERS)
    boundary = PRINT_BACKGROUND_RGB if suffix else None
    return suffix, boundary


def _cache_key(colors: Colors, layer_count: int, layer_height: float, pruned: bool,
               backing_suffix: Optional[str], background_rgb: Optional[tuple]) -> tuple:
    if backing_suffix is None:
        backing_suffix, background_rgb = _default_backing_key_parts(colors)
    return (
        colors_key(colors),
        layer_count,
        layer_height,
        pruned,
        backing_suffix,
        None if background_rgb is None else tuple(background_rgb),
    )


def get_cached_matrices(
    colors: Colors,
    layer_count: int,
    layer_height: float,
    pruned: bool = False,
    backing_suffix: Optional[str] = None,
    background_rgb: Optional[tuple] = None,
) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """Return cached matrices for this exact configuration, or None."""
    key = _cache_key(colors, layer_count, layer_height, pruned, backing_suffix, background_rgb)
    cached = _MATRIX_CACHE.get(key)
    if cached is not None:
        _MATRIX_CACHE.move_to_end(key)
    return cached


def set_cached_matrices(
    colors: Colors,
    layer_count: int,
    layer_height: float,
    ref_code_matrix: pd.DataFrame,
    ref_rgb_matrix: pd.DataFrame,
    pruned: bool = False,
    backing_suffix: Optional[str] = None,
    background_rgb: Optional[tuple] = None,
) -> None:
    """Store matrices for this configuration, evicting the oldest entry."""
    key = _cache_key(colors, layer_count, layer_height, pruned, backing_suffix, background_rgb)
    _MATRIX_CACHE[key] = (ref_code_matrix, ref_rgb_matrix)
    _MATRIX_CACHE.move_to_end(key)
    while len(_MATRIX_CACHE) > _MAX_ENTRIES:
        _MATRIX_CACHE.popitem(last=False)


def compute_and_cache_matrices(
    preset_name: str,
    layer_count: int,
    layer_height: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute (or fetch cached) matrices for a named preset configuration.

    Warms the DEFAULT app backing configuration (three white backing layers), the
    same one compute_reference_matrices resolves for backing_layers=None."""
    from services.stl_generator import compute_reference_matrices

    configs = _color_config.get_preset(preset_name)
    if configs is None:
        raise ValueError(f"Unknown preset: {preset_name}")
    return compute_reference_matrices(layer_count, layer_height, Colors.from_configs(configs))


def warmup_cache(
    preset_names: Optional[list[str]] = None,
    layer_counts: Optional[list[int]] = None,
    layer_heights: Optional[list[float]] = None,
) -> int:
    """
    Pre-compute and cache matrices for common configurations.

    Args:
        preset_names: Presets to warm up (default: all available presets)
        layer_counts: Layer counts to warm up (default: [4, 5])
        layer_heights: Layer heights to warm up (default: [0.08])

    Returns:
        Number of cache entries created
    """
    if preset_names is None:
        preset_names = _color_config.get_available_presets()
    if layer_counts is None:
        layer_counts = [4, 5]
    if layer_heights is None:
        layer_heights = [0.08]

    count = 0
    for preset_name in preset_names:
        for layer_count in layer_counts:
            for layer_height in layer_heights:
                try:
                    compute_and_cache_matrices(preset_name, layer_count, layer_height)
                    count += 1
                except Exception:
                    # Skip configurations that fail (e.g. too many permutations)
                    pass
    return count


def clear_cache() -> None:
    """Clear all cached matrices."""
    _MATRIX_CACHE.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "size": len(_MATRIX_CACHE),
        "keys": [repr(key) for key in _MATRIX_CACHE.keys()],
    }
