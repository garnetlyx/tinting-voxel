"""Base-10 per-channel transmission with one shared stacking rule."""
import functools
import logging
import unicodedata
from typing import Optional

import numpy as np

from core.color_materials import Color

logger = logging.getLogger(__name__)

def _normalize_code(code: str) -> str:
    if code is None:
        return ""
    # Remove whitespace and normalize to uppercase ASCII letters only
    # This handles Unicode combining characters and other edge cases
    normalized = unicodedata.normalize('NFD', code)
    return "".join(c.upper() for c in normalized if c.isascii() and c.isalpha())


def _build_color_map_from_key(color_key: tuple) -> dict:
    """Rebuild materials from their immutable optical cache key."""
    return {label: Color(label, td, hex_value) for label, td, hex_value in color_key}


def _validate_code(code: str, color_map: dict) -> None:
    for c in code:
        if c not in color_map:
            available = ", ".join(sorted(color_map.keys()))
            raise ValueError(
                f"Unknown color label '{c}' in blend code '{code}'. "
                f"Available labels: {available}"
            )


def _coerce_layer_height(layer_height: float) -> float:
    # Handle NaN and infinity
    if not np.isfinite(layer_height):
        return 0.0
    if layer_height < 0:
        return 0.0
    return float(layer_height)


def _normalize_background_rgb(background_rgb: Optional[tuple]) -> np.ndarray:
    if background_rgb is None:
        return np.ones(3, dtype=np.float64)

    bg = np.array(background_rgb, dtype=np.float64).reshape(-1)
    if bg.size != 3:
        raise ValueError(
            f"background_rgb must contain exactly 3 channels, got {background_rgb}"
        )
    return np.clip(bg, 0.0, 255.0) / 255.0


def _compose_light_loss_allocation(
    code: str,
    transmissions: list,
    color_map: dict,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """Allocate light loss across layers and the backing."""
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)
    if len(transmissions) != n:
        raise ValueError(
            f"Expected {n} layer transmissions, got {len(transmissions)}"
        )

    background = _normalize_background_rgb(background_rgb)
    remain = np.ones(3)
    light_loss = np.zeros((n + 1, 3))
    for i, transmission in enumerate(transmissions):
        t_ch = np.broadcast_to(
            np.asarray(transmission, dtype=np.float64),
            (3,),
        )
        t_ch = np.clip(np.nan_to_num(t_ch, nan=0.0), 0.0, 1.0)
        light_loss[i] = remain * (1.0 - t_ch)
        remain *= t_ch
    light_loss[n] = remain

    total = light_loss.sum(axis=0)
    total = np.where(total > 0, total, 1.0)
    light_loss /= total

    backing_weight = light_loss[n]
    rgb = np.ones(3)
    for i, label in enumerate(code):
        rgb -= color_map[label].get_absorption() * light_loss[i]
    rgb = backing_weight * background + (1.0 - backing_weight) * rgb
    return tuple(np.clip(rgb * 255.0, 0.0, 255.0))


def _blend_unified(
    code: str,
    layer_height: float,
    color_map: dict,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """Blend one stack code with the unified extinction formula."""
    layer_height = _coerce_layer_height(layer_height)
    if not code:
        return (255.0, 255.0, 255.0)
    transmissions = [
        color_map[c].transmission(layer_height)
        for c in code
    ]
    return _compose_light_loss_allocation(
        code, transmissions, color_map, background_rgb=background_rgb,
    )


def blend_tables(layer_height: float, color_key: tuple) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Material labels with their per-layer transmission and absorption rows."""
    layer_height = _coerce_layer_height(layer_height)
    color_map = _build_color_map_from_key(color_key)
    labels = list(color_map.keys())
    t_table = np.empty((len(labels), 3), dtype=np.float64)
    absorb_table = np.empty((len(labels), 3), dtype=np.float64)
    for i, label in enumerate(labels):
        t_table[i] = color_map[label].transmission(layer_height)
        absorb_table[i] = color_map[label].get_absorption()
    return labels, t_table, absorb_table


def rgb_from_indices(
    idx: np.ndarray,
    t_table: np.ndarray,
    absorb_table: np.ndarray,
    background_rgb=None,
) -> np.ndarray:
    """Blend index-encoded stack codes (codes, layers) to 0-255 float RGB.

    Each color's per-layer transmission is position-independent, so the
    whole light-loss allocation reduces to cumulative products over (codes,
    layers, channels). Numerically equivalent to _blend_unified per code.
    """
    background = _normalize_background_rgb(background_rgb)
    transmissions = t_table[idx]                           # (n, L, 3)
    remain_before = np.concatenate(
        [
            np.ones((len(idx), 1, 3), dtype=np.float64),
            np.cumprod(transmissions, axis=1)[:, :-1],
        ],
        axis=1,
    )
    loss = remain_before * (1.0 - transmissions)           # (n, L, 3)
    backing = np.prod(transmissions, axis=1)               # (n, 3)
    total = loss.sum(axis=1) + backing                     # ~1 by telescoping
    total = np.where(total > 0, total, 1.0)[:, None, :]
    loss /= total
    backing_weight = backing / total[:, 0, :]              # (n, 3)

    absorption = absorb_table[idx]                         # (n, L, 3)
    rgb = 1.0 - (absorption * loss).sum(axis=1)            # (n, 3)
    rgb = (
        backing_weight * background[None, :]
        + (1.0 - backing_weight) * rgb
    )
    return np.clip(rgb * 255.0, 0.0, 255.0)


def codes_to_rgb_batch(
    codes,
    layer_height: float,
    color_key: tuple,
    background_rgb=None,
    chunk_size: int = 65536,
) -> list[tuple]:
    """Blend many stack codes with the per-code invariants hoisted out of
    the loop (see rgb_from_indices)."""
    labels, t_table, absorb_table = blend_tables(layer_height, color_key)
    label_idx = {label: i for i, label in enumerate(labels)}

    out: list[tuple] = []
    normalized = [_normalize_code(code) for code in codes]
    for start in range(0, len(normalized), chunk_size):
        chunk = normalized[start:start + chunk_size]
        idx = np.array(
            [[label_idx[c] for c in code] for code in chunk], dtype=np.int64
        )
        out.extend(rgb_from_indices(idx, t_table, absorb_table, background_rgb).tolist())
    return out


@functools.lru_cache(maxsize=65536)
def _code_to_rgb_cached(
    code: str,
    layer_height: float,
    color_key: tuple,
) -> tuple:
    code = _normalize_code(code)
    if not code:
        return (255.0, 255.0, 255.0)

    color_map = _build_color_map_from_key(color_key)
    _validate_code(code, color_map)
    return _blend_unified(code, layer_height, color_map)


def clear_rgb_cache():
    _code_to_rgb_cached.cache_clear()


def rgb_cache_info():
    return _code_to_rgb_cached.cache_info()
