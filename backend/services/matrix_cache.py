"""
Reference matrix cache for color blend computations.

Caches the (code, rgb) reference matrices produced by
compute_reference_matrices, keyed by everything that influences the result:
the filament blend parameters (Colors._color_key), blend alpha and mode,
layer count/height, and the prune flag. Content addressing means custom
configurations cache exactly like named presets — no preset-name special
casing.

The cache is a small LRU: entries are pandas DataFrames whose size grows
with the candidate count (full 5-color x 8-layer enumeration is ~390k
codes), so only the most recent configurations are retained.
"""
import logging
from collections import OrderedDict
from typing import Optional

import pandas as pd

from core.blend_color import Colors, colors_key
from core import color_config as _color_config

logger = logging.getLogger(__name__)

# Cache key: (color_key, layer_count, layer_height, prune)
_MATRIX_CACHE: OrderedDict[tuple, tuple[pd.DataFrame, pd.DataFrame]] = OrderedDict()
_MAX_ENTRIES = 8


def _cache_key(colors: Colors, layer_count: int, layer_height: float, prune: Optional[bool]) -> tuple:
    return (
        colors_key(colors),
        layer_count,
        layer_height,
        prune,
    )


def get_cached_matrices(
    colors: Colors,
    layer_count: int,
    layer_height: float,
    prune: Optional[bool] = None,
) -> Optional[tuple[pd.DataFrame, pd.DataFrame]]:
    """Return cached matrices for this exact configuration, or None."""
    key = _cache_key(colors, layer_count, layer_height, prune)
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
    prune: Optional[bool] = None,
) -> None:
    """Store matrices for this configuration, evicting the oldest entry."""
    key = _cache_key(colors, layer_count, layer_height, prune)
    _MATRIX_CACHE[key] = (ref_code_matrix, ref_rgb_matrix)
    _MATRIX_CACHE.move_to_end(key)
    while len(_MATRIX_CACHE) > _MAX_ENTRIES:
        _MATRIX_CACHE.popitem(last=False)


def compute_and_cache_matrices(
    preset_name: str,
    layer_count: int,
    layer_height: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute (or fetch cached) matrices for a named preset configuration."""
    from services.stl_generator import compute_reference_matrices

    configs = _color_config.get_preset(preset_name)
    if configs is None:
        raise ValueError(f"Unknown preset: {preset_name}")
    colors = Colors.from_configs(configs)
    cached = get_cached_matrices(colors, layer_count, layer_height)
    if cached is not None:
        return cached
    code_df, rgb_df = compute_reference_matrices(layer_count, layer_height, colors)
    return code_df, rgb_df


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
