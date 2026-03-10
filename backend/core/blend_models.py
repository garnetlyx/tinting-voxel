import functools
from typing import Optional

import numpy as np

from core.color_materials import Color

HYBRID_PER_COLOR_BLEND_MODES = {
    "hybrid_calibrated",
    "hybrid_per_color_k",
    "hybrid_per_color_k_td1s_gamma",
}

VALID_BLEND_MODES = {
    "original",
    "kromacut",
    "per_channel",
    "hybrid",
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
    return "".join(code.split()).upper()


def _build_color_map_from_key(color_key: tuple) -> dict:
    color_map = {}
    for item in color_key:
        label = item[0]
        td = item[1]
        hex_val = item[2]
        k = item[3] if len(item) >= 5 else Color.DEFAULT_K
        alpha = item[4] if len(item) >= 5 else Color.DEFAULT_ALPHA
        td_scale = item[5] if len(item) >= 6 else Color.DEFAULT_TD_SCALE
        td_gamma = item[6] if len(item) >= 7 else Color.DEFAULT_TD_GAMMA
        c = Color(
            label,
            td,
            hex_val,
            alpha=alpha,
            k=k,
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
    layer_height = _coerce_layer_height(layer_height)
    background = _normalize_background_rgb(background_rgb)
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)

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
