import functools
from typing import Optional

import numpy as np

from core.color_materials import Color

HYBRID_PER_COLOR_BLEND_MODES = {
    "hybrid_calibrated",
    "hybrid_per_color_k",
    "hybrid_per_color_k_td1s_gamma",
    "hybrid_per_channel_k",
}

VALID_BLEND_MODES = {
    "original",
    "kromacut",
    "per_channel",
    "hybrid",
    "beer_lambert_td_rgb",
    *HYBRID_PER_COLOR_BLEND_MODES,
}


def validate_blend_mode(blend_mode: str) -> str:
    if blend_mode not in VALID_BLEND_MODES:
        valid = ", ".join(sorted(VALID_BLEND_MODES))
        raise ValueError(
            f"Invalid blend_mode '{blend_mode}'. Valid modes: {valid}"
        )
    return blend_mode


def _normalize_code(code: str) -> str:
    if code is None:
        return ""
    # Remove whitespace and normalize to uppercase ASCII letters only
    # This handles Unicode combining characters and other edge cases
    import unicodedata
    # Normalize to decomposed form (NFD), then filter only ASCII letters
    normalized = unicodedata.normalize('NFD', code)
    return "".join(c.upper() for c in normalized if c.isascii() and c.isalpha())


def _build_color_map_from_key(color_key: tuple) -> dict:
    color_map = {}
    for item in color_key:
        label = item[0]
        td = item[1]
        hex_val = item[2]
        k = item[3] if len(item) >= 4 else Color.DEFAULT_K
        alpha = item[4] if len(item) >= 5 else Color.DEFAULT_ALPHA
        td_scale = item[5] if len(item) >= 6 else Color.DEFAULT_TD_SCALE
        td_gamma = item[6] if len(item) >= 7 else Color.DEFAULT_TD_GAMMA
        k_rgb = item[7] if len(item) >= 8 else None
        td_rgb = item[8] if len(item) >= 9 else None
        c = Color(
            label,
            td,
            hex_val,
            alpha=alpha,
            k=k,
            k_rgb=k_rgb,
            td_rgb=td_rgb,
            td_scale=td_scale,
            td_gamma=td_gamma,
        )
        color_map[label] = c
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


def _blend_original(
    code: str,
    layer_height: float,
    color_map: dict,
    alpha: float = 12.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    # Handle empty color_map gracefully
    if not color_map:
        return (255.0, 255.0, 255.0)
    # Validate alpha is positive
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError(
            f"alpha must be finite and positive, got {alpha}"
        )
    # Validate all code characters are known colors
    unknown = [c for c in code if c not in color_map]
    if unknown:
        raise ValueError(
            f"blend code contains unknown color characters: {unknown}. "
            f"Valid colors: {list(color_map.keys())}"
        )
    layer_height = _coerce_layer_height(layer_height)
    background = _normalize_background_rgb(background_rgb)
    transmission = [
        Color.get_transmission_rate(layer_height, color_map[c].td, alpha=alpha)
        for c in code
    ]

    remain = 1
    array_size = max(len(code), 4) + 1
    light_loss_ratio = np.zeros(array_size)

    for i, t in enumerate(transmission):
        light_loss_ratio[i] = remain * (1 - t)
        remain *= t
    light_loss_ratio[len(code)] = remain

    light_loss_ratio = light_loss_ratio / np.sum(light_loss_ratio)

    bg = light_loss_ratio[len(code)]
    rgb = np.ones(3)
    for i, c in enumerate(code):
        color = color_map[c]
        rgb -= color.get_absorption() * light_loss_ratio[i]
    rgb = bg * background + (1 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _blend_kromacut(
    code: str,
    layer_height: float,
    color_map: dict,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    layer_height = _coerce_layer_height(layer_height)
    LN10 = np.log(10)
    result = _normalize_background_rgb(background_rgb) * 255.0

    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t = 0.0
        else:
            t = np.exp(-LN10 * layer_height / td)
        opacity = 1.0 - t
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * opacity + result * t

    return tuple(np.clip(result, 0, 255))


def _blend_per_channel(
    code: str,
    layer_height: float,
    color_map: dict,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    layer_height = _coerce_layer_height(layer_height)
    result = _normalize_background_rgb(background_rgb) * 255.0

    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            absorption = color.get_absorption()
            t_ch = np.exp(-absorption * layer_height / td)
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * (1.0 - t_ch) + result * t_ch

    return tuple(np.clip(result, 0, 255))


def _blend_beer_lambert_td_rgb(
    code: str,
    layer_height: float,
    color_map: dict,
    k_residual: float = 0.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """Per-channel measured-TD transmission (Phase-8 staircase mode).

    Each layer attenuates channel ch by t_ch = 10^(-d / td_rgb[ch]); layers
    composite sequentially over the backing with the filament's nominal RGB
    as the opaque limit. td_rgb values come from direct staircase
    measurement in the app's round-trip gamma-space convention, so no
    per-channel parameters are fitted. Colors without td_rgb fall back to
    their scalar td on all three channels (e.g. a grey with only a TD1S
    reading). The optional scalar k_residual * A_ch term models residual
    pigment attenuation beyond the measured TD; it defaults to 0 because
    td_rgb already carries the spectral information.
    """
    layer_height = _coerce_layer_height(layer_height)
    LN10 = np.log(10)
    result = _normalize_background_rgb(background_rgb) * 255.0

    for c in code:
        color = color_map[c]
        td_rgb = getattr(color, "td_rgb", None)
        if td_rgb is not None:
            td_ch = np.array(td_rgb, dtype=np.float64)
        else:
            td_ch = np.full(3, float(color.td), dtype=np.float64)
        with np.errstate(divide="ignore"):
            rate = np.where(td_ch > 0, LN10 * layer_height / td_ch, np.inf)
        if k_residual > 0.0:
            rate = rate + k_residual * color.get_absorption() * layer_height
        t_ch = np.exp(-rate)
        t_ch = np.clip(np.nan_to_num(t_ch, nan=0.0), 0.0, 1.0)
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * (1.0 - t_ch) + result * t_ch

    return tuple(np.clip(result, 0, 255))


def _blend_hybrid(
    code: str,
    layer_height: float,
    color_map: dict,
    scatter_alpha: float = 5.0,
    k: float = 10.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    layer_height = _coerce_layer_height(layer_height)
    background = _normalize_background_rgb(background_rgb)
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)

    # Validate scatter_alpha is positive
    if not np.isfinite(scatter_alpha) or scatter_alpha <= 0:
        raise ValueError(
            f"scatter_alpha must be finite and positive, got {scatter_alpha}"
        )

    # Validate all code characters are known colors
    unknown = [c for c in code if c not in color_map]
    if unknown:
        raise ValueError(
            f"blend code contains unknown color characters: {unknown}. "
            f"Valid colors: {list(color_map.keys())}"
        )

    transmissions = []
    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            scatter = scatter_alpha / td
            absorption = color.get_absorption()
            t_ch = np.exp(-(scatter + k * absorption) * layer_height)
            t_ch = np.clip(t_ch, 0, 1)
        transmissions.append(t_ch)

    remain = np.ones(3)
    array_size = max(n, 4) + 1
    light_loss = np.zeros((array_size, 3))
    for i, t_ch in enumerate(transmissions):
        light_loss[i] = remain * (1.0 - t_ch)
        remain *= t_ch
    light_loss[n] = remain

    total = light_loss.sum(axis=0)
    total = np.where(total > 0, total, 1.0)
    light_loss /= total

    bg = light_loss[n]
    rgb = np.ones(3)
    for i, c in enumerate(code):
        color = color_map[c]
        rgb -= color.get_absorption() * light_loss[i]
    rgb = bg * background + (1.0 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _blend_hybrid_per_color(
    code: str,
    layer_height: float,
    color_map: dict,
    scatter_alpha: float = 5.0,
    k_map: Optional[dict] = None,
    default_k: float = 10.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    # Handle empty color_map gracefully
    if not color_map:
        return (255.0, 255.0, 255.0)
    layer_height = _coerce_layer_height(layer_height)
    background = _normalize_background_rgb(background_rgb)
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)

    # Validate scatter_alpha is positive
    if not np.isfinite(scatter_alpha) or scatter_alpha <= 0:
        raise ValueError(
            f"scatter_alpha must be finite and positive, got {scatter_alpha}"
        )

    k_map = k_map or {}
    transmissions = []
    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            scatter = scatter_alpha / td
            k_c = float(k_map.get(c, default_k))
            absorption = color.get_absorption()
            t_ch = np.exp(-(scatter + k_c * absorption) * layer_height)
            t_ch = np.clip(t_ch, 0, 1)
        transmissions.append(t_ch)

    remain = np.ones(3)
    array_size = max(n, 4) + 1
    light_loss = np.zeros((array_size, 3))
    for i, t_ch in enumerate(transmissions):
        light_loss[i] = remain * (1.0 - t_ch)
        remain *= t_ch
    light_loss[n] = remain

    total = light_loss.sum(axis=0)
    total = np.where(total > 0, total, 1.0)
    light_loss /= total

    bg = light_loss[n]
    rgb = np.ones(3)
    for i, c in enumerate(code):
        color = color_map[c]
        rgb -= color.get_absorption() * light_loss[i]
    rgb = bg * background + (1.0 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _blend_hybrid_per_color_sequential(
    code: str,
    layer_height: float,
    color_map: dict,
    scatter_alpha: float = 5.0,
    k_map: Optional[dict] = None,
    default_k: float = 10.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """Ablation: identical per-layer transmission as `_blend_hybrid_per_color`,
    but composited by sequential linear interpolation from the backing
    (result = nominal_rgb*(1-t) + result*t) instead of the light-loss
    allocation of Eqs. 4--8. Isolates whether the allocation stacking form
    contributes beyond the hybrid transmission itself.
    """
    if not color_map:
        return (255.0, 255.0, 255.0)
    layer_height = _coerce_layer_height(layer_height)
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)
    if not np.isfinite(scatter_alpha) or scatter_alpha <= 0:
        raise ValueError(
            f"scatter_alpha must be finite and positive, got {scatter_alpha}"
        )
    k_map = k_map or {}
    result = _normalize_background_rgb(background_rgb) * 255.0
    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            scatter = scatter_alpha / td
            k_c = float(k_map.get(c, default_k))
            t_ch = np.exp(-(scatter + k_c * color.get_absorption()) * layer_height)
            t_ch = np.clip(t_ch, 0, 1)
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * (1.0 - t_ch) + result * t_ch
    return tuple(np.clip(result, 0, 255))


def _blend_hybrid_per_channel_k(
    code: str,
    layer_height: float,
    color_map: dict,
    scatter_alpha: float = 5.0,
    default_k: float = 10.0,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    """
    Hybrid blend with per-channel scattering coefficients (k_rgb).

    This implements Proposal A from docs/CALIBRATION.md:
    - Each color has per-channel k values (k_R, k_G, k_B)
    - Allows modeling channel-selective scattering (e.g., Cyan reflects R)
    - Formula: T_ch = exp(-(scatter + k_rgb * absorption) * layer_height)

    Falls back to scalar k if k_rgb is not defined for a color.
    """
    if not color_map:
        return (255.0, 255.0, 255.0)
    layer_height = _coerce_layer_height(layer_height)
    background = _normalize_background_rgb(background_rgb)
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)

    if not np.isfinite(scatter_alpha) or scatter_alpha <= 0:
        raise ValueError(
            f"scatter_alpha must be finite and positive, got {scatter_alpha}"
        )

    transmissions = []
    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            scatter = scatter_alpha / td
            absorption = color.get_absorption()

            # Use per-channel k_rgb if available, otherwise fall back to scalar k
            if color.k_rgb is not None:
                k_per_ch = np.array(color.k_rgb, dtype=np.float64)
            else:
                k_scalar = getattr(color, 'k', default_k)
                k_per_ch = np.full(3, k_scalar, dtype=np.float64)

            # Per-channel transmission: exp(-(scatter + k_ch * A_ch) * d)
            scatter_per_ch = scatter + k_per_ch * absorption
            t_ch = np.exp(-scatter_per_ch * layer_height)
            t_ch = np.clip(t_ch, 0, 1)
        transmissions.append(t_ch)

    remain = np.ones(3)
    array_size = max(n, 4) + 1
    light_loss = np.zeros((array_size, 3))
    for i, t_ch in enumerate(transmissions):
        light_loss[i] = remain * (1.0 - t_ch)
        remain *= t_ch
    light_loss[n] = remain

    total = light_loss.sum(axis=0)
    total = np.where(total > 0, total, 1.0)
    light_loss /= total

    bg = light_loss[n]
    rgb = np.ones(3)
    for i, c in enumerate(code):
        color = color_map[c]
        rgb -= color.get_absorption() * light_loss[i]
    rgb = bg * background + (1.0 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _build_k_map(color_map: dict) -> dict[str, float]:
    return {label: float(color.k) for label, color in color_map.items()}


def _effective_td(color: Color, blend_mode: str) -> float:
    if blend_mode not in {"hybrid_calibrated", "hybrid_per_color_k_td1s_gamma"}:
        return color.td
    if color.td <= 0:
        return 0.0
    return float(color.td_scale) * (float(color.td) ** float(color.td_gamma))


def _effective_color_map(color_map: dict, blend_mode: str) -> dict:
    if blend_mode not in {"hybrid_calibrated", "hybrid_per_color_k_td1s_gamma"}:
        return color_map

    remapped = {}
    for label, color in color_map.items():
        remapped[label] = Color(
            color.name,
            _effective_td(color, blend_mode),
            color.hex,
            alpha=color.alpha,
            k=color.k,
            k_rgb=getattr(color, 'k_rgb', None),
            td_scale=color.td_scale,
            td_gamma=color.td_gamma,
        )
    return remapped


def _blend_by_mode(
    code: str,
    layer_height: float,
    color_map: dict,
    alpha: float = 12.0,
    blend_mode: str = "original",
    k_map: Optional[dict] = None,
    background_rgb: Optional[tuple] = None,
) -> tuple:
    validate_blend_mode(blend_mode)
    code = _normalize_code(code)
    if not code:
        return (255.0, 255.0, 255.0)
    if blend_mode == "kromacut":
        return _blend_kromacut(
            code,
            layer_height,
            color_map,
            background_rgb=background_rgb,
        )
    if blend_mode == "per_channel":
        return _blend_per_channel(
            code,
            layer_height,
            color_map,
            background_rgb=background_rgb,
        )
    if blend_mode == "beer_lambert_td_rgb":
        return _blend_beer_lambert_td_rgb(
            code,
            layer_height,
            color_map,
            background_rgb=background_rgb,
        )
    if blend_mode == "hybrid":
        base_k = next(iter(color_map.values())).k if color_map else Color.DEFAULT_K
        return _blend_hybrid(
            code,
            layer_height,
            color_map,
            scatter_alpha=alpha,
            k=base_k,
            background_rgb=background_rgb,
        )
    if blend_mode == "hybrid_per_channel_k":
        return _blend_hybrid_per_channel_k(
            code,
            layer_height,
            color_map,
            scatter_alpha=alpha,
            background_rgb=background_rgb,
        )
    if blend_mode in HYBRID_PER_COLOR_BLEND_MODES:
        return _blend_hybrid_per_color(
            code,
            layer_height,
            _effective_color_map(color_map, blend_mode),
            scatter_alpha=alpha,
            k_map=k_map if k_map is not None else _build_k_map(color_map),
            background_rgb=background_rgb,
        )
    return _blend_original(
        code,
        layer_height,
        color_map,
        alpha=alpha,
        background_rgb=background_rgb,
    )


@functools.lru_cache(maxsize=4096)
def _code_to_rgb_cached(
    code: str,
    layer_height: float,
    color_key: tuple,
    alpha: float = 12.0,
    blend_mode: str = "original",
) -> tuple:
    code = _normalize_code(code)
    if not code:
        return (255.0, 255.0, 255.0)

    color_map = _build_color_map_from_key(color_key)
    _validate_code(code, color_map)
    return _blend_by_mode(code, layer_height, color_map, alpha=alpha, blend_mode=blend_mode)


def clear_rgb_cache():
    _code_to_rgb_cached.cache_clear()


def rgb_cache_info():
    return _code_to_rgb_cached.cache_info()
