from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from PIL import ImageColor
from skimage.color import rgb2lab

if TYPE_CHECKING:
    from core.color_config import ColorConfig


class Color:
    DEFAULT_HEX = {
        "C": "#00FFFF",
        "M": "#FF00FF",
        "Y": "#FFFF00",
        "W": "#FFFFFF",
    }

    def __init__(self, name, transmission_distance, hex=None, absorption=None, rgb=None):
        if not name or not name[0].isalpha() or not name[0].isascii():
            raise ValueError(
                f"Color name must start with an ASCII letter (A-Z, a-z): {name}. "
                f"The first character is used as the blend code identifier."
            )

        self.name = name
        self.td = transmission_distance
        self.rgb = rgb
        self.absorption = absorption

        if hex is None:
            hex = self.DEFAULT_HEX.get(self.get_label())

        if hex is None:
            raise ValueError(
                f"hex is required for non-default color name '{name}'. "
                f"Only CMYW colors have default hex values."
            )

        self.update_hex(hex)

    def __repr__(self):
        return self.name

    def update_hex(self, hex):
        self.hex = hex
        self.rgb = ImageColor.getcolor(self.hex, "RGB")
        self.cmyk = self.get_cmyk()
        self.absorption = self.get_absorption()

    def get_label(self):
        return self.name[0].upper()

    def get_cmyk(self, rgb_scale=255, cmyk_scale=1):
        r, g, b = self.rgb
        if (r, g, b) == (0, 0, 0):
            return 0, 0, 0, cmyk_scale

        c = 1 - r / rgb_scale
        m = 1 - g / rgb_scale
        y = 1 - b / rgb_scale

        min_cmy = min(c, m, y)
        c = (c - min_cmy) / (1 - min_cmy)
        m = (m - min_cmy) / (1 - min_cmy)
        y = (y - min_cmy) / (1 - min_cmy)
        k = min_cmy

        return c * cmyk_scale, m * cmyk_scale, y * cmyk_scale, k * cmyk_scale

    def get_absorption(self):
        rate = (255 - np.array(self.rgb)) / 255
        return rate

    @staticmethod
    def get_transmission_rate(d, td, alpha=12):
        if td <= 0:
            return 0.0
        x = alpha * d / td
        return np.exp(-x)

    @staticmethod
    def get_lab(rgb):
        rgb_normalized = np.array(rgb) / 255.0
        lab = rgb2lab(np.array([rgb_normalized]))
        L, a, b = lab[0, 0], lab[0, 1], lab[0, 2]
        C = np.sqrt(a**2 + b**2)
        return L, a, b, C

    @staticmethod
    def is_neutral(rgb, threshold=10):
        L, a, b, C = Color.get_lab(rgb)
        return C < threshold or np.std(rgb) < threshold

    @staticmethod
    def is_brown(rgb):
        L, a, b, C = Color.get_lab(rgb)
        return L < 60 and a > 5 and b > 10 and C < 70

    @staticmethod
    def map_to_nearest_color(input_colors, reference_code, reference_rgb):
        ref_colors = []
        ref_blend_codes = []

        for r_idx in range(reference_code.shape[0]):
            for c_idx in range(reference_code.shape[1]):
                code = reference_code.iat[r_idx, c_idx]
                rgb = reference_rgb.iat[r_idx, c_idx]
                ref_colors.append(rgb)
                ref_blend_codes.append(code)

        ref_colors = np.array(ref_colors) / 255.0
        ref_lab = rgb2lab(ref_colors.reshape(-1, 1, 3)).reshape(-1, 3)

        inp = np.array(input_colors) / 255.0
        inp_lab = rgb2lab(inp.reshape(-1, 1, 3)).reshape(-1, 3)

        results_code = []
        results_color = []
        for lab_color in inp_lab:
            dists = np.linalg.norm(ref_lab - lab_color, axis=1)
            nearest_idx = np.argmin(dists)
            results_code.append(ref_blend_codes[nearest_idx])
            results_color.append(np.round(ref_colors[nearest_idx] * 255).astype(int))

        return results_code, results_color


class Colors:
    from core.color_config import BAMBU_CMYK_PRESET, CLEAR_CMYK_PRESET

    _BAMBU_PRESET = {c.label: c for c in BAMBU_CMYK_PRESET}
    _CLEAR_PRESET = {c.label: c for c in CLEAR_CMYK_PRESET}
    PRIMARY_COLORS = [c.label for c in BAMBU_CMYK_PRESET]

    DEFAULT_TD = {c.label: c.transmission_distance for c in BAMBU_CMYK_PRESET}
    BAMBU_CMYK_HEX = {c.label: c.hex for c in BAMBU_CMYK_PRESET}
    DEFAULT_CLEAR_TD = {c.label: c.transmission_distance for c in CLEAR_CMYK_PRESET}
    CLEAR_CMYK_HEX = {c.label: c.hex for c in CLEAR_CMYK_PRESET}

    def __init__(self, colors=None, clear=False, names=None):
        self.colors = colors if colors is not None else {}
        self.white_balance = {"r": 0, "g": 10, "b": 24}

        if colors is not None:
            return

        preset = self._CLEAR_PRESET if clear else self._BAMBU_PRESET
        labels = names if names is not None else self.PRIMARY_COLORS

        for c in labels:
            cfg = preset.get(c)
            if cfg is None:
                raise ValueError(
                    f"Unknown color label '{c}'. "
                    f"Valid labels: {list(preset.keys())}"
                )
            self.colors[c] = Color(c, cfg.transmission_distance, cfg.hex)

    def __len__(self):
        return len(self.colors)

    def __getitem__(self, label):
        label = label.strip().upper()
        if label not in self.colors:
            available = ", ".join(sorted(self.colors.keys()))
            raise KeyError(
                f"Color label '{label}' not found. Available labels: {available}"
            )
        return self.colors[label]

    def __setitem__(self, label, value=None):
        self.colors[label.strip().upper()] = value

    def add(self, color):
        self.colors[color.get_label()] = color

    def update_white_balance(self, new_r, new_g, new_b):
        self.white_balance["r"] = new_r
        self.white_balance["g"] = new_g
        self.white_balance["b"] = new_b

    def get_labels(self):
        return [x for x in self.colors]

    @classmethod
    def from_configs(cls, configs) -> "Colors":
        from core.color_config import ColorConfig

        if len(configs) < 4:
            raise ValueError(
                f"Color configuration requires at least 4 colors, got {len(configs)}. "
                f"Use the default CMYK preset or provide 4+ custom filament colors."
            )

        instance = cls(colors={})

        for config in configs:
            label = config.label
            if not label.isascii():
                raise ValueError(
                    f"Color label '{label}' from name '{config.name}' is not ASCII. "
                    f"Color names must start with an ASCII letter (A-Z, a-z). "
                    f"The first character is used as the blend code identifier."
                )
            if label in instance.colors:
                raise ValueError(
                    f"Duplicate color label '{label}' from name '{config.name}'. "
                    f"Each color must have a unique first letter."
                )
            color = Color(
                name=config.name,
                transmission_distance=config.transmission_distance,
                hex=config.hex,
            )
            instance.colors[label] = color

        return instance
