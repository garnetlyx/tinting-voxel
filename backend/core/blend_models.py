import functools
from typing import Optional

import numpy as np

from core.color_materials import Color


def _build_color_map_from_key(color_key: tuple) -> dict:
    color_map = {}
    for label, td, hex_val in color_key:
        color_map[label] = Color(label, td, hex_val)
    return color_map


def _validate_code(code: str, color_map: dict) -> None:
    for c in code:
        if c not in color_map:
            available = ", ".join(sorted(color_map.keys()))
            raise ValueError(
                f"Unknown color label '{c}' in blend code '{code}'. "
                f"Available labels: {available}"
            )


def _blend_original(code: str, layer_height: float, color_map: dict, alpha: float = 12.0) -> tuple:
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
    rgb = bg * np.ones(3) + (1 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _blend_kromacut(code: str, layer_height: float, color_map: dict) -> tuple:
    LN10 = np.log(10)
    result = np.array([255.0, 255.0, 255.0])

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


def _blend_per_channel(code: str, layer_height: float, color_map: dict) -> tuple:
    result = np.array([255.0, 255.0, 255.0])

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
) -> tuple:
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
    rgb = bg * np.ones(3) + (1.0 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


def _blend_hybrid_per_color(
    code: str,
    layer_height: float,
    color_map: dict,
    scatter_alpha: float = 5.0,
    k_map: Optional[dict] = None,
    default_k: float = 10.0,
) -> tuple:
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
    rgb = bg * np.ones(3) + (1.0 - bg) * rgb
    return tuple(np.clip(rgb * 255, 0, 255))


@functools.lru_cache(maxsize=4096)
def _code_to_rgb_cached(
    code: str,
    layer_height: float,
    color_key: tuple,
    alpha: float = 12.0,
    blend_mode: str = "original",
) -> tuple:
    if not code:
        return (255.0, 255.0, 255.0)

    color_map = _build_color_map_from_key(color_key)
    _validate_code(code, color_map)

    if blend_mode == "kromacut":
        return _blend_kromacut(code, layer_height, color_map)
    if blend_mode == "per_channel":
        return _blend_per_channel(code, layer_height, color_map)

    return _blend_original(code, layer_height, color_map, alpha=alpha)


def clear_rgb_cache():
    _code_to_rgb_cached.cache_clear()


def rgb_cache_info():
    return _code_to_rgb_cached.cache_info()
