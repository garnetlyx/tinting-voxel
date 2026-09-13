from typing import TYPE_CHECKING

import numpy as np
from PIL import ImageColor
from skimage.color import rgb2lab

if TYPE_CHECKING:
    from core.color_config import ColorConfig


class Color:
    # Baseline "no absorption correction". Calibrated families set k
    # explicitly (e.g. bambu phase6 k=8.13); 0 makes default-parameter
    # colors blend as plain Beer-Lambert t = exp(-alpha*d/td).
    DEFAULT_K = 0.0
    DEFAULT_HEX = {
        "C": "#00FFFF",
        "M": "#FF00FF",
        "Y": "#FFFF00",
        "W": "#FFFFFF",
    }

    def __init__(
        self,
        name,
        transmission_distance,
        hex=None,
        absorption=None,
        rgb=None,
        k=DEFAULT_K,
        display_name=None,
    ):
        """A filament color: hex + td + k — the complete blend description.

        td (mm) is channel-neutral (one composite number, broadcast to all
        channels); k is the optional pigment absorption gain (default 0).
        Historical calibration fields (alpha, k_rgb, td_rgb, td_neutral,
        td_scale, td_gamma) were fold points of the retired mode dispatch —
        deleted; git history for archaeology.
        """
        if not name or not name[0].isalpha() or not name[0].isascii():
            raise ValueError(
                f"Color name must start with an ASCII letter (A-Z, a-z): {name}. "
                f"The first character is used as the blend code identifier."
            )
        if not np.isfinite(float(transmission_distance)):
            raise ValueError(
                f"transmission_distance must be finite and not NaN, got {transmission_distance}"
            )
        if transmission_distance < 0:
            raise ValueError(
                f"transmission_distance must be >= 0, got {transmission_distance}"
            )
        if not np.isfinite(float(k)):
            raise ValueError(
                f"k must be finite and not NaN, got {k}"
            )
        if k < 0:
            raise ValueError(
                f"k must be non-negative, got {k}"
            )

        self.name = name
        self.td = transmission_distance
        self.rgb = rgb
        self.absorption = absorption
        self.k = k
        self.display_name = display_name

        if hex is None and rgb is not None:
            if len(rgb) != 3:
                raise ValueError(f"rgb must be a 3-tuple, got: {rgb}")
            rgb = tuple(int(channel) for channel in rgb)
            hex = "#{:02X}{:02X}{:02X}".format(*rgb)
        elif hex is None:
            hex = self.DEFAULT_HEX.get(self.get_label())

        if hex is None:
            raise ValueError(
                f"hex is required for non-default color name '{name}'. "
                f"Only CMYW colors have default hex values."
            )

        self.update_hex(hex)

    def __repr__(self):
        return self.display_name or self.name

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
        denominator = 1 - min_cmy
        if denominator <= 1e-12:
            return 0.0, 0.0, 0.0, min_cmy * cmyk_scale

        c = (c - min_cmy) / denominator
        m = (m - min_cmy) / denominator
        y = (y - min_cmy) / denominator
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
    def perceptual_distance_raw(lab_color, ref_lab):
        """Plain CIEDE2000 distance, without the dark-color adjustments."""
        from skimage.color import deltaE_ciede2000

        lab_color = np.asarray(lab_color, dtype=np.float64).reshape(3)
        ref_lab = np.asarray(ref_lab, dtype=np.float64).reshape(-1, 3)
        return np.asarray(deltaE_ciede2000(
            lab_color.reshape(1, 1, 3), ref_lab.reshape(-1, 1, 3), channel_axis=-1,
        )).reshape(-1)

    @staticmethod
    def perceptual_distance(lab_color, ref_lab):
        """CIEDE2000 with dark-color adjustments — the map_to_nearest_color metric.

        For dark chromatic sources, hue differences are penalized harder
        (CIEDE2000 underweights hue in dark colors); for dark neutrals,
        low-chroma candidates are preferred.
        """
        from skimage.color import deltaE_ciede2000

        lab_color = np.asarray(lab_color, dtype=np.float64).reshape(3)
        ref_lab = np.asarray(ref_lab, dtype=np.float64).reshape(-1, 3)
        dists = np.asarray(deltaE_ciede2000(
            lab_color.reshape(1, 1, 3), ref_lab.reshape(-1, 1, 3), channel_axis=-1,
        )).reshape(-1)

        source_L, source_a, source_b = lab_color
        source_chroma = np.sqrt(source_a**2 + source_b**2)

        if source_L < 40 and source_chroma > 8:
            ref_a = ref_lab[:, 1]
            ref_b = ref_lab[:, 2]
            ref_chromas = np.sqrt(ref_a**2 + ref_b**2)

            source_hue = np.arctan2(source_b, source_a)
            ref_hues = np.arctan2(ref_b, ref_a)

            hue_diff = np.abs(source_hue - ref_hues)
            hue_diff = np.minimum(hue_diff, 2 * np.pi - hue_diff)

            darkness_factor = (40 - source_L) / 40
            chroma_factor = np.minimum(source_chroma / 20, 1.0)
            hue_penalty = hue_diff * darkness_factor * chroma_factor * 25
            dists = dists + hue_penalty
        elif source_L < 35 and source_chroma <= 8:
            ref_chromas = np.sqrt(ref_lab[:, 1]**2 + ref_lab[:, 2]**2)
            darkness_factor = (35 - source_L) / 35
            chroma_penalty = ref_chromas * darkness_factor * 1.5
            dists = dists + chroma_penalty

        return dists

    @staticmethod
    def map_to_nearest_color(input_colors, reference_code, reference_rgb, weights=None):
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
            dists = Color.perceptual_distance(lab_color, ref_lab)
            nearest_idx = int(np.argmin(dists))
            results_code.append(ref_blend_codes[nearest_idx])
            results_color.append(np.round(ref_colors[nearest_idx] * 255).astype(int))

        return results_code, results_color


class Colors:
    from core.color_config import BAMBU_CMYW_PHASE6_PRESET, CLEAR_CMYW_PRESET

    _BAMBU_PRESET = {c.label: c for c in BAMBU_CMYW_PHASE6_PRESET}
    _CLEAR_PRESET = {c.label: c for c in CLEAR_CMYW_PRESET}


    def __init__(self, colors=None, clear=False, names=None):
        self.colors = colors if colors is not None else {}
        self.white_balance = {"r": 0, "g": 10, "b": 24}

        if colors is not None:
            return

        preset = self._CLEAR_PRESET if clear else self._BAMBU_PRESET
        labels = names if names is not None else list(preset)

        for c in labels:
            cfg = preset.get(c)
            if cfg is None:
                raise ValueError(
                    f"Unknown color label '{c}'. "
                    f"Valid labels: {list(preset.keys())}"
                )
            self.colors[c] = Color(
                cfg.name,
                cfg.transmission_distance,
                cfg.hex,
                k=cfg.k,
                display_name=cfg.label,
            )

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

        if configs is None:
            raise ValueError(
                "Color configuration cannot be None. "
                "Pass a list of ColorConfig objects or use a preset."
            )
        if len(configs) < 4:
            raise ValueError(
                f"Color configuration requires at least 4 colors, got {len(configs)}. "
                f"Use a built-in preset or provide 4+ custom filament colors."
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
                k=config.k,
            )
            instance.colors[label] = color

        return instance
