from typing import TYPE_CHECKING

import numpy as np
from PIL import ImageColor
from skimage.color import rgb2lab

if TYPE_CHECKING:
    from core.color_config import ColorConfig


class Color:
    # Baseline "no absorption correction". Calibrated families set k
    # explicitly (e.g. bambu A-standard k_C = 3.4996); 0 blends as plain
    # Beer-Lambert.
    DEFAULT_K = 0.0
    # Neutral scalar-form compensation: Eqs. (1)-(2) with
    # alpha_s = ln 10, s_td = gamma_td = 1 degrade to ln(10)/td + k*A_ch.
    LN10 = float(np.log(10.0))
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
        td_rgb=None,
        alpha_s=LN10,
        td_scale=1.0,
        td_gamma=1.0,
        display_name=None,
    ):
        """A filament color: hex + td + k (+ optional per-channel td_rgb,
        + optional scalar-form capture compensation alpha_s/td_scale/td_gamma).

        Two characterizations of td, same forward family — there is no
        clear/regular material distinction:
        - td_rgb present (staircase-measured, paper form (i)):
          mu_ch = ln(10)/td_rgb[ch] + k*A_ch.
        - scalar td (paper Eqs. (1)-(2)):
          mu_ch = alpha_s/(td_scale * td**td_gamma) + k*A_ch.
          td is the raw scalar TD reading; td_scale/td_gamma are the fitted
          s_td/gamma_td remap and alpha_s the fitted scatter coefficient of
          the calibrated set. Neutral defaults (alpha_s = ln 10,
          td_scale = td_gamma = 1) degrade to plain ln(10)/td + k*A_ch.
        W is a semi-opaque neutral scatterer through the same formula
        (A_ch = 0, mu = alpha_s/td_eff, finite) — never treated as a
        transparent or special layer.
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
        if td_rgb is not None:
            td_rgb = tuple(float(ch) for ch in td_rgb)
            if len(td_rgb) != 3:
                raise ValueError(
                    f"td_rgb must be exactly 3 per-channel distances [R, G, B], got {td_rgb}"
                )
            for ch_idx, td_ch in enumerate(td_rgb):
                if not np.isfinite(td_ch) or td_ch <= 0:
                    raise ValueError(
                        f"td_rgb channel {'RGB'[ch_idx]} must be positive and finite, got {td_ch}"
                    )
        if not np.isfinite(float(k)):
            raise ValueError(
                f"k must be finite and not NaN, got {k}"
            )
        if k < 0:
            raise ValueError(
                f"k must be non-negative, got {k}"
            )
        for field_name, value in (
            ("alpha_s", alpha_s), ("td_scale", td_scale), ("td_gamma", td_gamma),
        ):
            if not np.isfinite(float(value)) or float(value) <= 0:
                raise ValueError(
                    f"{field_name} must be positive and finite, got {value}"
                )

        self.name = name
        self.td = transmission_distance
        self.td_rgb = td_rgb
        self.rgb = rgb
        self.absorption = absorption
        self.k = k
        self.alpha_s = float(alpha_s)
        self.td_scale = float(td_scale)
        self.td_gamma = float(td_gamma)
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
    def get_transmission_rate(d, td):
        """Single-layer transmission under the unified base-10 convention:
        t = 10^(-d/td). Non-positive td means fully opaque."""
        if td <= 0:
            return 0.0
        return float(10.0 ** (-d / td))

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
        # Vectorized extraction: iterating 800k+ pandas cells with .iat costs
        # seconds on full-enumeration matrices; flattened arrays are equivalent.
        ref_blend_codes = list(reference_code.values.flatten())
        ref_colors = np.array(list(reference_rgb.values.flatten())) / 255.0
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
    from core.color_config import BAMBU_CMYW_PHASE6_PRESET

    _DEFAULT_PRESET = {c.label: c for c in BAMBU_CMYW_PHASE6_PRESET}


    def __init__(self, colors=None, names=None):
        """A filament set. No clear/regular distinction: a set is just its
        colors (each described by hex + td (+ td_rgb) + k). The default set
        when none is given is the bambu CMYW preset."""
        self.colors = colors if colors is not None else {}

        if colors is not None:
            return

        preset = self._DEFAULT_PRESET
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
                td_rgb=cfg.td_rgb,
                alpha_s=cfg.alpha_s,
                td_scale=cfg.td_scale,
                td_gamma=cfg.td_gamma,
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
                td_rgb=config.td_rgb,
                alpha_s=config.alpha_s,
                td_scale=config.td_scale,
                td_gamma=config.td_gamma,
            )
            instance.colors[label] = color

        return instance
