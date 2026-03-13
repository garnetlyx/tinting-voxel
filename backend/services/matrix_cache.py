"""
Reference matrix cache for color blend computations.

Pre-computes and caches reference matrices for preset configurations
to avoid redundant computation during image processing.
"""
from typing import Optional, Tuple
import pandas as pd
from functools import lru_cache

from core.blend_color import Colors
from core.color_config import get_preset


# Cache key: (preset_name, layer_count, layer_height)
# Cache value: (ref_code_matrix, ref_rgb_matrix)
_MATRIX_CACHE: dict[Tuple[str, int, float], Tuple[pd.DataFrame, pd.DataFrame]] = {}


def get_cache_key(
    preset_name: Optional[str],
    layer_count: int,
    layer_height: float,
) -> Optional[Tuple[str, int, float]]:
    """
    Generate cache key for matrix lookup.
    
    Returns None if preset_name is None (custom colors, not cacheable).
    """
    if preset_name is None:
        return None
    return (preset_name, layer_count, layer_height)


def get_cached_matrices(
    preset_name: Optional[str],
    layer_count: int,
    layer_height: float,
) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Get cached reference matrices for a preset configuration.
    
    Args:
        preset_name: Name of the preset (e.g., "bambu_cmyk")
        layer_count: Number of color layers
        layer_height: Height of each layer in mm
        
    Returns:
        Tuple of (ref_code_matrix, ref_rgb_matrix) if cached, None otherwise
    """
    cache_key = get_cache_key(preset_name, layer_count, layer_height)
    if cache_key is None:
        return None
    return _MATRIX_CACHE.get(cache_key)


def set_cached_matrices(
    preset_name: Optional[str],
    layer_count: int,
    layer_height: float,
    ref_code_matrix: pd.DataFrame,
    ref_rgb_matrix: pd.DataFrame,
) -> None:
    """
    Store reference matrices in cache for a preset configuration.
    
    Args:
        preset_name: Name of the preset
        layer_count: Number of color layers
        layer_height: Height of each layer in mm
        ref_code_matrix: Reference code matrix
        ref_rgb_matrix: Reference RGB matrix
    """
    cache_key = get_cache_key(preset_name, layer_count, layer_height)
    if cache_key is not None:
        _MATRIX_CACHE[cache_key] = (ref_code_matrix, ref_rgb_matrix)


def compute_and_cache_matrices(
    preset_name: str,
    layer_count: int,
    layer_height: float,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute reference matrices for a preset and cache them.
    
    Args:
        preset_name: Name of the preset
        layer_count: Number of color layers
        layer_height: Height of each layer in mm
        
    Returns:
        Tuple of (ref_code_matrix, ref_rgb_matrix)
        
    Raises:
        ValueError: If preset not found or computation fails
    """
    from services.stl_generator import compute_reference_matrices
    
    # Get preset configuration
    configs = get_preset(preset_name)
    if configs is None:
        raise ValueError(f"Unknown preset: {preset_name}")
    
    # Create Colors instance
    colors = Colors.from_configs(configs)
    
    # Compute matrices
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layer_count, layer_height, colors
    )
    
    # Cache the result
    set_cached_matrices(
        preset_name, layer_count, layer_height,
        ref_code_matrix, ref_rgb_matrix
    )
    
    return ref_code_matrix, ref_rgb_matrix


def warmup_cache(
    preset_names: Optional[list[str]] = None,
    layer_counts: Optional[list[int]] = None,
    layer_heights: Optional[list[float]] = None,
) -> int:
    """
    Pre-compute and cache matrices for common configurations.
    
    Args:
        preset_names: List of preset names to warm up (default: all available presets)
        layer_counts: List of layer counts to warm up (default: [4, 5, 6, 7, 8])
        layer_heights: List of layer heights to warm up (default: [0.08])
        
    Returns:
        Number of cache entries created
    """
    from core.color_config import get_available_presets
    
    if preset_names is None:
        # Warm up all available presets (Phase 6 only by default)
        preset_names = get_available_presets()
    
    if layer_counts is None:
        layer_counts = [4, 5, 6, 7, 8]
    
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
                    # Skip presets that fail (e.g., too many permutations)
                    pass
    
    return count


def clear_cache() -> None:
    """Clear all cached matrices."""
    _MATRIX_CACHE.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    return {
        "size": len(_MATRIX_CACHE),
        "keys": list(_MATRIX_CACHE.keys()),
    }
