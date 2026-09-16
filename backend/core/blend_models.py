"""
The unified blend model for stacked translucent filaments.

ONE formula, zero mode dispatch:

    mu_ch(color) = ln(10) / td + k * A_ch(color)
    t_ch         = exp(-mu_ch * layer_height)
    stack color  = light-loss allocation (paper Eqs. 4--8)

Every filament — calibrated preset or user-entered custom — is described by
exactly three values: hex, td (one transmission distance in mm, broadcast to
all channels), and an optional pigment absorption gain k (default 0).
Channel selectivity comes solely from the k * A_ch term (A_ch is the
per-channel darkness derived from hex); td itself is channel-neutral.

Provenance of preset values (see the research repo):
- bambu presets: td = ln10 * td_scale * td_td1s**td_gamma / alpha_s, the exact
  algebraic fold of the Phase-6 fitted scatter term, plus the fitted k —
  predictions are bit-identical to the fitted hybrid model.
- clear preset: td = arithmetic mean of the staircase-measured per-channel
  TDs, k = 0.

Historical blend modes (original / kromacut / per_channel / hybrid family /
beer_lambert_td_rgb) were stages of the calibration research; the paper's
final model is the single formula above. Deleted — git history for
archaeology, research repo engine pin for reproduction.
"""
import functools
import logging
import unicodedata
from typing import Optional

import numpy as np

from core.color_materials import Color

logger = logging.getLogger(__name__)

LN10 = float(np.log(10.0))


def _normalize_code(code: str) -> str:
    if code is None:
        return ""
    # Remove whitespace and normalize to uppercase ASCII letters only
    # This handles Unicode combining characters and other edge cases
    normalized = unicodedata.normalize('NFD', code)
    return "".join(c.upper() for c in normalized if c.isascii() and c.isalpha())


def _build_color_map_from_key(color_key: tuple) -> dict:
    """Rebuild Color objects from the cache key
    (label, td, hex, k, td_rgb, alpha_s, td_scale, td_gamma)."""
    color_map = {}
    for label, td, hex_val, k, td_rgb, alpha_s, td_scale, td_gamma in color_key:
        color_map[label] = Color(
            label, td, hex_val, k=k, td_rgb=td_rgb,
            alpha_s=alpha_s, td_scale=td_scale, td_gamma=td_gamma,
        )
    return color_map


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


def _resolve_extinction(color) -> np.ndarray:
    """Per-channel extinction coefficient (1/mm), paper forward model.

    Staircase characterization (td_rgb present, paper form (i)):
        mu_ch = ln(10)/td_rgb[ch] + k*A_ch
    Scalar characterization (paper Eqs. (1)-(2)):
        td_eff = td_scale * td**td_gamma
        mu_ch = alpha_s/td_eff + k*A_ch
    Neutral defaults (alpha_s = ln 10, td_scale = td_gamma = 1) degrade the
    scalar form to ln(10)/td + k*A_ch. A non-positive td means fully
    opaque: mu = inf, t = 0. No filament-type flags — td shape alone
    selects the branch.
    """
    absorption = color.get_absorption()
    k = float(color.k)
    td_rgb = color.td_rgb
    if td_rgb is not None:
        td_ch = np.asarray(td_rgb, dtype=np.float64)
        mu = np.where(td_ch > 0, LN10 / np.where(td_ch > 0, td_ch, 1.0), np.inf)
    else:
        td = float(color.td)
        if td <= 0:
            return np.full(3, np.inf)
        td_eff = float(color.td_scale) * (td ** float(color.td_gamma))
        mu = np.full(3, float(color.alpha_s) / td_eff)
    return mu + k * absorption


def _compose_light_loss_allocation(
    code: str,
    transmissions: list,
    color_map: dict,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """Compose per-layer transmissions with the paper's Eqs. 4--8."""
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
        np.exp(-_resolve_extinction(color_map[c]) * layer_height)
        for c in code
    ]
    return _compose_light_loss_allocation(
        code, transmissions, color_map, background_rgb=background_rgb,
    )


def codes_to_rgb_batch(
    codes,
    layer_height: float,
    color_key: tuple,
    background_rgb=None,
    chunk_size: int = 65536,
) -> list[tuple]:
    """Blend many stack codes with the per-code invariants hoisted out of
    the loop.

    Full enumeration explodes combinatorially (e.g. 5 colors x 8 layers =
    390,625 codes); blending them one at a time recomputes per-color
    constants for every code. Vectorized chunk-wise over codes — each
    color's per-layer transmission is position-independent, so the whole
    light-loss allocation reduces to cumulative products over (codes,
    layers, channels). Numerically equivalent to _blend_unified per code.
    """
    layer_height = _coerce_layer_height(layer_height)
    color_map = _build_color_map_from_key(color_key)
    labels = list(color_map.keys())
    label_idx = {label: i for i, label in enumerate(labels)}

    t_table = np.empty((len(labels), 3), dtype=np.float64)
    absorb_table = np.empty((len(labels), 3), dtype=np.float64)
    for i, label in enumerate(labels):
        t_table[i] = np.exp(-_resolve_extinction(color_map[label]) * layer_height)
        absorb_table[i] = color_map[label].get_absorption()

    background = _normalize_background_rgb(background_rgb)

    out: list[tuple] = []
    normalized = [_normalize_code(code) for code in codes]
    for start in range(0, len(normalized), chunk_size):
        chunk = normalized[start:start + chunk_size]
        idx = np.array(
            [[label_idx[c] for c in code] for code in chunk], dtype=np.int64
        )
        transmissions = t_table[idx]                       # (n, L, 3)
        remain_before = np.concatenate(
            [
                np.ones((len(chunk), 1, 3), dtype=np.float64),
                np.cumprod(transmissions, axis=1)[:, :-1],
            ],
            axis=1,
        )
        loss = remain_before * (1.0 - transmissions)       # (n, L, 3)
        backing = np.prod(transmissions, axis=1)           # (n, 3)
        total = loss.sum(axis=1) + backing                 # ~1 by telescoping
        total = np.where(total > 0, total, 1.0)[:, None, :]
        loss /= total
        backing_weight = backing / total[:, 0, :]          # (n, 3)

        absorption = absorb_table[idx]                     # (n, L, 3)
        rgb = 1.0 - (absorption * loss).sum(axis=1)        # (n, 3)
        rgb = (
            backing_weight * background[None, :]
            + (1.0 - backing_weight) * rgb
        )
        rgb = np.clip(rgb * 255.0, 0.0, 255.0)
        out.extend(rgb.tolist())
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
