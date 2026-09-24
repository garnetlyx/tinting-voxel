from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from config.print_defaults import DEFAULT_FILAMENT_PRESET
from core.parallel import worker_threads
from core.color_config import get_preset, normalize_transmission_distance

import numpy as np
from PIL import ImageColor
from skimage.color import rgb2lab

if TYPE_CHECKING:
    from core.color_config import ColorConfig

# Below this many (reference x input) pairs, thread startup outweighs the gain.
PARALLEL_MATCH_MIN_PAIRS = 1_000_000
# CIEDE2000 scoring allocates dozens of temporaries the size of its input, so
# references are scored in slices of this many colors: memory per thread stays
# bounded however many references a stack search keeps, with identical scores.
DISTANCE_CHUNK = 65_536


def _score_in_chunks(score, lab_color, ref_lab) -> np.ndarray:
    """score(lab_color, ref_slice) over ref_lab, DISTANCE_CHUNK references at a time."""
    lab_color = np.asarray(lab_color, dtype=np.float64).reshape(3)
    ref_lab = np.asarray(ref_lab, dtype=np.float64).reshape(-1, 3)
    out = np.empty(len(ref_lab))
    for start in range(0, len(ref_lab), DISTANCE_CHUNK):
        out[start:start + DISTANCE_CHUNK] = score(lab_color, ref_lab[start:start + DISTANCE_CHUNK])
    return out


def _ciede2000(lab_color: np.ndarray, ref_lab: np.ndarray) -> np.ndarray:
    from skimage.color import deltaE_ciede2000

    return np.asarray(deltaE_ciede2000(
        lab_color.reshape(1, 1, 3), ref_lab.reshape(-1, 1, 3), channel_axis=-1,
    )).reshape(-1)


def _penalized_ciede2000(lab_color: np.ndarray, ref_lab: np.ndarray) -> np.ndarray:
    """CIEDE2000 with dark-color adjustments.

    For dark chromatic sources, hue differences are penalized harder
    (CIEDE2000 underweights hue in dark colors); for dark neutrals,
    low-chroma candidates are preferred.
    """
    dists = _ciede2000(lab_color, ref_lab)

    source_L, source_a, source_b = lab_color
    source_chroma = np.sqrt(source_a**2 + source_b**2)

    if source_L < 40 and source_chroma > 8:
        source_hue = np.arctan2(source_b, source_a)
        ref_hues = np.arctan2(ref_lab[:, 2], ref_lab[:, 1])

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


class Color:
    def __init__(
        self,
        name,
        transmission_distance,
        hex,
        display_name=None,
    ):
        """A filament color with scalar or RGB-channel transmission distance."""
        if not name or not name[0].isalpha() or not name[0].isascii():
            raise ValueError(
                f"Color name must start with an ASCII letter (A-Z, a-z): {name}. "
                f"The first character is used as the blend code identifier."
            )
        self.name = name
        self.td = normalize_transmission_distance(transmission_distance)
        self.display_name = display_name

        self.update_hex(hex)

    def __repr__(self):
        return self.display_name or self.name

    def update_hex(self, hex):
        self.hex = hex
        self.rgb = ImageColor.getcolor(self.hex, "RGB")

    def get_label(self):
        return self.name[0].upper()

    def get_absorption(self):
        rate = (255 - np.array(self.rgb)) / 255
        return rate

    @property
    def td_channels(self) -> tuple[float, float, float]:
        """A scalar explicitly describes equal transmission in all channels."""
        if isinstance(self.td, tuple):
            return self.td
        return (self.td, self.td, self.td)

    def transmission(self, layer_height: float) -> np.ndarray:
        return np.power(10.0, -layer_height / np.asarray(self.td_channels))

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
        return _score_in_chunks(_ciede2000, lab_color, ref_lab)

    @staticmethod
    def perceptual_distance(lab_color, ref_lab):
        """CIEDE2000 with dark-color adjustments — the map_to_nearest_color metric
        (see _penalized_ciede2000)."""
        return _score_in_chunks(_penalized_ciede2000, lab_color, ref_lab)

    @staticmethod
    def map_to_nearest_color(
        input_colors: "list[tuple[int, int, int]] | np.ndarray",
        reference_code,
        reference_rgb,
    ) -> "tuple[list[str], list[tuple[int, int, int]]]":
        """Nearest printable blend per input color under the production metric."""
        # Vectorized extraction: iterating 800k+ pandas cells with .iat costs
        # seconds on full-enumeration matrices; flattened arrays are equivalent.
        ref_blend_codes = list(reference_code.values.flatten())
        ref_colors = np.array(list(reference_rgb.values.flatten())) / 255.0
        ref_lab = rgb2lab(ref_colors.reshape(-1, 1, 3)).reshape(-1, 3)

        inp = np.array(input_colors) / 255.0
        inp_lab = rgb2lab(inp.reshape(-1, 1, 3)).reshape(-1, 3)

        def nearest(lab_color) -> int:
            return int(np.argmin(Color.perceptual_distance(lab_color, ref_lab)))

        # Each input is an independent vectorized pass over the references;
        # numpy releases the GIL, so large matches spread across threads.
        if worker_threads() > 1 and len(inp_lab) > 1 and len(ref_lab) * len(inp_lab) >= PARALLEL_MATCH_MIN_PAIRS:
            with ThreadPoolExecutor(max_workers=worker_threads()) as pool:
                nearest_indices = list(pool.map(nearest, inp_lab))
        else:
            nearest_indices = [nearest(lab_color) for lab_color in inp_lab]

        results_code = [ref_blend_codes[i] for i in nearest_indices]
        results_color = [np.round(ref_colors[i] * 255).astype(int) for i in nearest_indices]
        return results_code, results_color


class Colors:

    def __init__(self, colors=None, names=None):
        """A filament set. No clear/regular distinction: a set is just its
        colors (each described by hex and transmission distance). The default set
        when none is given is the configured default preset."""
        self.colors = colors if colors is not None else {}

        if colors is not None:
            return

        preset = {c.label: c for c in get_preset(DEFAULT_FILAMENT_PRESET)}
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
            )
            instance.colors[label] = color

        return instance
