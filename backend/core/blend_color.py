import ast
import colorsys
import functools
import itertools
import logging
import math
import os.path
import re
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from PIL import Image, ImageColor, ImageDraw
from skimage.color import rgb2lab
from stl import mesh

if TYPE_CHECKING:
    from core.color_config import ColorConfig

logger = logging.getLogger(__name__)


class Color:
    DEFAULT_HEX = {
                'C': '#00FFFF',  # Cyan
                'M': "#FF00FF",  # Magenta
                'Y': '#FFFF00',  # Yellow
                'W': '#FFFFFF',  # White
            }
    def __init__(self, name, transmission_distance, hex=None, absorption=None, rgb = None):
        # Validate that name starts with ASCII letter (used as label in blend codes)
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
        self.rgb = ImageColor.getcolor(self.hex, 'RGB')
        self.cmyk = self.get_cmyk()
        self.absorption = self.get_absorption()

    def get_label(self):
        return self.name[0].upper()

    def get_cmyk(self, rgb_scale = 255, cmyk_scale = 1):
        r, g, b = self.rgb
        if (r, g, b) == (0, 0, 0):
            # black: C=0, M=0, Y=0, K=1
            return 0, 0, 0, cmyk_scale

        # rgb [0,255] -> cmy [0,1]
        c = 1 - r / rgb_scale
        m = 1 - g / rgb_scale
        y = 1 - b / rgb_scale

        # extract out k [0, 1]
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
        # Beer–Lambert law
        if td <= 0:
            return 0.0  # Fully opaque for zero/negative transmission distance
        x = alpha * d  / td
        T = np.exp(- x) # transmission rate
        return T

    @staticmethod
    def get_lab(rgb):
        rgb_normalized = np.array(rgb) / 255.0  # Convert [0,255] to [0,1]
        lab = rgb2lab(np.array([rgb_normalized]))  # rgb2lab expects shape (1, 3) or (H, W, 3)
        L, a, b = lab[0, 0], lab[0, 1], lab[0, 2]
        C = np.sqrt(a**2 + b**2)
        return L, a, b, C

    @staticmethod
    def is_neutral(rgb, threshold = 10):
        L, a, b, C = Color.get_lab(rgb)
        return C < threshold or np.std(rgb) < threshold

    @staticmethod
    def is_brown(rgb):
        L, a, b, C = Color.get_lab(rgb)
        return L < 60 and a > 5 and b > 10 and C < 70

    @staticmethod
    def map_to_nearest_color(input_colors, reference_code, reference_rgb):
        """
        For each input RGB tuple, find the closest RGB tuple in a reference matrix.
        Distance is computed in LAB color space (perceptual).

        Parameters:
            input_colors (list of tuples): e.g. [(R,G,B), ...]
            reference_matrix (list of lists): 2D matrix [[(R,G,B),...], [...]]
                                            OR cells may be (code, rgb_tuple)

        Returns:
            result list of blend code for each color
        """

        # ----------- Extract pure RGB tuples from reference matrix ------------
        ref_colors = []
        ref_blend_codes = []
        coords = []   # store (row,col) mapping

        for r_idx in range(reference_code.shape[0]):
            for c_idx in range(reference_code.shape[1]):
                code = reference_code.iat[r_idx, c_idx]
                rgb = reference_rgb.iat[r_idx, c_idx]
                ref_colors.append(rgb)
                ref_blend_codes.append(code)
                coords.append((r_idx, c_idx))


        ref_colors = np.array(ref_colors) / 255.0
        ref_lab = rgb2lab(ref_colors.reshape(-1, 1, 3)).reshape(-1, 3)

        # ----------- Convert input to LAB ------------
        inp = np.array(input_colors) / 255.0
        inp_lab = rgb2lab(inp.reshape(-1, 1, 3)).reshape(-1, 3)

        results_code = []
        results_color = []

        # ----------- For each input color, find nearest reference color --------
        for lab_color in inp_lab:
            # Compute Euclidean distance in LAB
            dists = np.linalg.norm(ref_lab - lab_color, axis=1)
            nearest_idx = np.argmin(dists)
            results_code.append(ref_blend_codes[nearest_idx])
            results_color.append(np.round(ref_colors[nearest_idx] * 255).astype(int))

        return results_code, results_color

@functools.lru_cache(maxsize=4096)
def _code_to_rgb_cached(code: str, layer_height: float, color_key: tuple,
                        alpha: float = 12.0, blend_mode: str = "original") -> tuple:
    """Cached computation of layered optical mixing using Beer-Lambert.

    Args:
        code: Color code string (e.g. "CMYW"), already stripped/uppercased.
        layer_height: Layer height in mm.
        color_key: Frozen tuple of (label, transmission_distance, hex) per color,
                   used as hashable cache key.
        alpha: Absorption coefficient for Beer-Lambert model.
        blend_mode: Blending algorithm — "original", "kromacut", or "per_channel".
    """
    if not code:
        return (255.0, 255.0, 255.0)

    # Rebuild color lookup from the hashable key
    color_map = {}
    for label, td, hex_val in color_key:
        color_map[label] = Color(label, td, hex_val)

    for c in code:
        if c not in color_map:
            available = ', '.join(sorted(color_map.keys()))
            raise ValueError(
                f"Unknown color label '{c}' in blend code '{code}'. "
                f"Available labels: {available}"
            )

    if blend_mode == "kromacut":
        return _blend_kromacut(code, layer_height, color_map)
    elif blend_mode == "per_channel":
        return _blend_per_channel(code, layer_height, color_map)

    # Original mode
    transmission = [
        Color.get_transmission_rate(layer_height, color_map[c].td, alpha=alpha)
        for c in code
    ]

    remain = 1
    array_size = max(len(code), 4) + 1  # min 4 for layer_count_max compat
    light_loss_ratio = np.zeros(array_size)

    for i, t in enumerate(transmission):
        light_loss_ratio[i] = remain * (1 - t)
        remain *= t
    # Background gets all remaining transmitted light (no extra absorption)
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
    """Mode A: Kromacut/HueForge-style blending.

    Scalar transmission T = 10^(-d/TD) with per-channel linear interpolation.
    Iterative: each layer blends onto previous result, starting from white.
    """
    LN10 = np.log(10)
    result = np.array([255.0, 255.0, 255.0])  # white background

    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t = 0.0
        else:
            t = np.exp(-LN10 * layer_height / td)  # T = 10^(-d/TD)
        opacity = 1.0 - t
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * opacity + result * t

    return tuple(np.clip(result, 0, 255))


def _blend_per_channel(code: str, layer_height: float, color_map: dict) -> tuple:
    """Mode B: Per-channel transmission blending.

    Each RGB channel has its own transmission rate derived from the filament's
    absorption in that channel: T_ch = exp(-absorption_ch * d / TD).
    """
    result = np.array([255.0, 255.0, 255.0])  # white background

    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            absorption = color.get_absorption()  # (255 - rgb) / 255 per channel
            t_ch = np.exp(-absorption * layer_height / td)  # per-channel T
        filament_rgb = np.array(color.rgb, dtype=np.float64)
        result = filament_rgb * (1.0 - t_ch) + result * t_ch

    return tuple(np.clip(result, 0, 255))


def _blend_hybrid(code: str, layer_height: float, color_map: dict,
                   scatter_alpha: float = 5.0, k: float = 10.0) -> tuple:
    """Hybrid blend: Original-style probabilistic stacking + per-channel transmission.

    Combines the proven stacking model from Original mode with per-channel
    transmission to handle selective absorption (CMY) correctly.

    T_ch = exp(-(scatter_alpha/td + k * absorption_ch) * layer_height)

    Where scatter_alpha/td provides channel-neutral base opacity (works for
    White/Black) and k * absorption_ch adds per-channel selective attenuation
    (works for CMY).
    """
    n = len(code)
    if n == 0:
        return (255.0, 255.0, 255.0)

    # Per-layer, per-channel transmission
    transmissions = []
    for c in code:
        color = color_map[c]
        td = color.td
        if td <= 0:
            t_ch = np.zeros(3)
        else:
            scatter = scatter_alpha / td
            absorption = color.get_absorption()  # (255 - rgb) / 255 per channel
            t_ch = np.exp(-(scatter + k * absorption) * layer_height)
            t_ch = np.clip(t_ch, 0, 1)
        transmissions.append(t_ch)

    # Original-style light distribution (per-channel)
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


def clear_rgb_cache():
    """Clear the code_to_rgb LRU cache."""
    _code_to_rgb_cached.cache_clear()


def rgb_cache_info():
    """Return cache statistics for code_to_rgb."""
    return _code_to_rgb_cached.cache_info()


class Colors:
    # Preset data derived from color_config.py (single source of truth)
    from core.color_config import BAMBU_CMYK_PRESET, CLEAR_CMYK_PRESET

    _BAMBU_PRESET = {c.label: c for c in BAMBU_CMYK_PRESET}
    _CLEAR_PRESET = {c.label: c for c in CLEAR_CMYK_PRESET}
    PRIMARY_COLORS = [c.label for c in BAMBU_CMYK_PRESET]

    # Keep these as derived views for backward compatibility with tests
    DEFAULT_TD = {c.label: c.transmission_distance for c in BAMBU_CMYK_PRESET}
    BAMBU_CMYK_HEX = {c.label: c.hex for c in BAMBU_CMYK_PRESET}
    DEFAULT_CLEAR_TD = {c.label: c.transmission_distance for c in CLEAR_CMYK_PRESET}
    CLEAR_CMYK_HEX = {c.label: c.hex for c in CLEAR_CMYK_PRESET}

    def __init__(self, colors=None, clear=False, names=None):
        self.colors = colors if colors is not None else {}
        self.white_balance = {
            'r': 0,
            'g': 10,
            'b': 24
        }

        # Skip default initialization if colors dict was provided
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
            available = ', '.join(sorted(self.colors.keys()))
            raise KeyError(
                f"Color label '{label}' not found. Available labels: {available}"
            )
        return self.colors[label]

    def __setitem__(self, label, value=None):
        label = label.strip().upper()
        self.colors[label] = value

    def add(self, color):
        self.colors[color.get_label()] = color

    def update_white_balance(self, new_r, new_g, new_b):
        self.white_balance['r'] = new_r
        self.white_balance['g'] = new_g
        self.white_balance['b'] = new_b

    def get_labels(self):
        """Return list of color labels in insertion order."""
        return [x for x in self.colors]

    @classmethod
    def from_configs(cls, configs) -> "Colors":
        """
        Create a Colors instance from a list of ColorConfig objects.

        Args:
            configs: List of ColorConfig objects defining each filament color

        Returns:
            Colors instance with configured colors

        Example:
            >>> from core.color_config import ColorConfig
            >>> configs = [
            ...     ColorConfig(name="Cyan", hex="#00FFFF", transmission_distance=3.0),
            ...     ColorConfig(name="Magenta", hex="#FF00FF", transmission_distance=1.9),
            ... ]
            >>> colors = Colors.from_configs(configs)
        """
        from core.color_config import ColorConfig

        # Enforce minimum 4 colors for proper CMYK color mixing
        if len(configs) < 4:
            raise ValueError(
                f"Color configuration requires at least 4 colors, got {len(configs)}. "
                f"Use the default CMYK preset or provide 4+ custom filament colors."
            )

        instance = cls(colors={})  # Empty dict, skip default initialization

        for config in configs:
            label = config.label
            # Validate that label is ASCII (first char of name must be ASCII letter)
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
                hex=config.hex
            )
            instance.colors[label] = color

        return instance

class BlendTestGenerator:
    def __init__(self, plate_length=13*16, plate_width=13*16, grid_length=13, grid_width=13, layer_height=.08, layer_count_max=4,
                 same_height=False, rearrange_by_size = True, sort_color=True, verbose = True,
                 directory = 'output',
                 colors = None,
                 alpha: float = 12.0,
                 blend_mode: str = "original"
                ):
        if layer_count_max <= 0:
            raise ValueError(f"layer_count_max must be positive, got {layer_count_max}")
        self.length_total = plate_length
        self.width_total = plate_width
        self.grid_length = grid_length
        self.grid_width = grid_width
        self.layer_height = layer_height
        self.layer_count_max = layer_count_max
        self.colors = colors if colors is not None else Colors()
        self.alpha = alpha
        self.blend_mode = blend_mode
        self.reshape = rearrange_by_size
        self.same_height = same_height
        self.sort_color = sort_color
        self.verbose = verbose
        color_labels = ''.join(self.colors.get_labels())
        self.filename = f'{color_labels}_{self.length_total}x{self.width_total}x{self.layer_height * self.layer_count_max:.2f}'
        self.directory = os.path.join(directory, self.filename) + '/'
        self.df_code = pd.DataFrame()
        self.df_rgb = pd.DataFrame()

    def reshape_matrix(self, df):
        # split
        split_num_x = df.shape[0] * df.shape[1] * self.grid_length // self.length_total
        # Guard against split_num_x being 0 before using it in division
        if split_num_x == 0:
            return df, self.grid_length, self.grid_width
        split_num_y = df.shape[0] * df.shape[1] // split_num_x

        if split_num_x > 0 and self.reshape:
            df = pd.DataFrame(np.reshape(df, (split_num_y, split_num_x)))
        else:
            df = df

        if self.verbose:
            logger.debug("Length per cell: %.2f, Width per cell: %s, Layer height: %s", self.grid_length, self.grid_width, self.layer_height)
            logger.debug("Total build volume: Length=%s, Width=%s, Height=%s", self.length_total, self.width_total, self.layer_height * self.layer_count_max)

        return df, self.grid_length, self.grid_width

    def merge_meshes_by_color(self, meshes):
        color_labels = ''.join(self.colors.get_labels())
        for color in meshes:
            filename = f'{color_labels}_{color}_{self.length_total}x{self.width_total}x{self.layer_height * self.layer_count_max:.2f}.stl'
            self.save_stl_mesh(self.merge_stl_meshes(meshes[color]), filename)

    def generate(self):
        if self.same_height:
            df = self.permutation_matrix(self.colors.get_labels(), self.layer_count_max)
        else:
            df = self.combined_permutation_matrix(self.colors.get_labels(), self.layer_count_max)


        # reshape based on plate dimension
        df, grid_length, grid_width = self.reshape_matrix(df)

        # generate rgb based on code
        df_rgb, df_code = self.set_code_rgb_df(df)

        meshes = {color: []  for color in self.colors.get_labels()}
        for y in range(df_code.shape[0]):
            for x in range(df_code.shape[1]):
                if not pd.isna(df_code.iat[y, x]):
                    code = df_code.iat[y, x]
                    for color_idx in range(len(code)):
                        color = code[color_idx]
                        x_range = [grid_length*(x), grid_length*(x+1)]
                        y_range = [grid_width*y, grid_width*(y+1)]
                        z_range = [self.layer_height * color_idx, self.layer_height * (color_idx + 1)]
                        meshes[color].append(self.generate_box(x_range, y_range, z_range))

        self.merge_meshes_by_color(meshes)
        self.save_matrix_csv()
        self.save_matrix_image()

        return df_rgb, df_code

    def combined_permutation_matrix(self, items, count):
        """
        Generate a combined permutation matrix for the given items and count.

        Args:
            items: List of color labels (e.g., ['C', 'M', 'Y', 'W'])
            count: Maximum layer count (must be >= 1).
                   count=1 returns only single-character codes.

        Returns:
            DataFrame with permutations grouped by first character.

        Raises:
            ValueError: If items is empty or count < 1.
        """
        if not items:
            raise ValueError("items list cannot be empty for combined_permutation_matrix")
        if count < 1:
            raise ValueError(f"count must be at least 1, got {count}")

        matrix = []
        for first in items:
            row = [first]
            for length in range(2, count + 1):
                combos = [first + ''.join(p) for p in itertools.product(items, repeat=length - 1)]
                row.extend(combos)
            matrix.append(row)
        max_len = max(len(r) for r in matrix)

        for r in matrix:
            while len(r) < max_len:
                r.append('[]')

        cols = [l for l in range(max_len)]
        rows = [r for r in range(len(items))]
        df = pd.DataFrame(matrix, index=rows, columns=cols)
        return df

    def permutation_matrix(self, items, count):
        """
        Generate a permutation matrix for the given items and count.
        """
        if not items:
            raise ValueError("items list cannot be empty for permutation_matrix")
        if count <= 0:
            raise ValueError(f"count must be positive, got {count}")
        perms = list(itertools.product(items, repeat=count))
        joined  = [''.join(p) for p in perms]
        row = len(items)
        col = len(joined) // row
        matrix = [joined[i*col:(i+1)*col] for i in range(row)]

        df = pd.DataFrame(matrix)
        return df

    def generate_box(self, xrange, yrange, zrange):
        """
        Create a 3D box mesh from the given coordinate ranges.
        """
        x1, x2 = xrange
        y1, y2 = yrange
        z1, z2 = zrange

        # Validate coordinates are non-negative
        if x1 < 0 or x2 < 0:
            raise ValueError(f"X coordinates must be non-negative, got ({x1}, {x2})")
        if y1 < 0 or y2 < 0:
            raise ValueError(f"Y coordinates must be non-negative, got ({y1}, {y2})")
        if z1 < 0 or z2 < 0:
            raise ValueError(f"Z coordinates must be non-negative, got ({z1}, {z2})")

        # Validate ranges are not inverted
        if x1 >= x2:
            raise ValueError(f"X range start must be less than end, got ({x1}, {x2})")
        if y1 >= y2:
            raise ValueError(f"Y range start must be less than end, got ({y1}, {y2})")
        if z1 >= z2:
            raise ValueError(f"Z range start must be less than end, got ({z1}, {z2})")

        vertices = np.array([
            [x1, y1, z1],
            [x2, y1, z1],
            [x2, y2, z1],
            [x1, y2, z1],
            [x1, y1, z2],
            [x2, y1, z2],
            [x2, y2, z2],
            [x1, y2, z2]
        ])

        faces = np.array([
            [0,3,1], [1,3,2],    # bottom
            [0,4,7], [0,7,3],    # left
            [4,5,6], [4,6,7],    # top
            [5,1,2], [5,2,6],    # right
            [2,3,6], [3,7,6],    # back
            [0,1,5], [0,5,4]     # front
        ])

        box = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, f in enumerate(faces):
            for j in range(3):
                box.vectors[i][j] = vertices[f[j], :]

        return box

    def merge_stl_meshes(self, mesh_list):
        """
        Merge multiple STL mesh objects into a single mesh.
        """
        # Calculate the total number of faces
        total_faces = sum(m.data.shape[0] for m in mesh_list)
        # Create a new Mesh to store all faces
        combined = mesh.Mesh(np.zeros(total_faces, dtype=mesh.Mesh.dtype))

        current_index = 0
        for m in mesh_list:
            n = m.data.shape[0]
            combined.data[current_index:current_index + n] = m.data
            current_index += n

        return combined


    def save_stl_mesh(self, mesh_obj, filename):
        """
        Save the given STL mesh object to a stl file.
        """

        file_path = os.path.join(self.directory, filename)
        os.makedirs(self.directory, exist_ok=True)
        mesh_obj.save(file_path)
        return mesh_obj

    def save_matrix_csv(self):
        """
        Save the given DataFrame to a CSV file.
        """

        file_path = os.path.join(self.directory, self.filename)
        os.makedirs(self.directory, exist_ok=True)
        self.df_rgb.to_csv(file_path+'_rgb.csv', index=False)
        self.df_code.to_csv(file_path+'_code.csv', index=False)

    def read_matrix_csv(self, filename):
        # read CSV forcing strings
        df_raw = pd.read_csv(os.path.join(self.directory, filename),
                            header=0, dtype=str)

        df_parsed = df_raw.map(self.parse_cell)
        return df_parsed

    def matrix_to_code_color_map(self, df_rgb, df_code):
        map = {}
        n_rows, n_cols = df_rgb.shape

        for r in range(n_rows):
            for c in range(n_cols):
                code = df_code.iloc[r, c]
                rgb = df_rgb.iloc[r, c]
                map[code] = rgb
        return map

    def set_code_rgb_df(self, df):
        """
        """
        records = []
        n_rows, n_cols = df.shape

        # Sort first by hue (left to right), then by lightness (top to bottom)
        df_rgb = pd.DataFrame(records)

        for r in range(n_rows):
            for c in range(n_cols):
                code = df.iloc[r, c]
                rgb = self.code_to_rgb(code)
                # code_to_rgb returns [0, 255] RGB values, normalize for colorsys
                h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
                tone = 2
                if Color.is_neutral(rgb, 15.5):
                    tone = 0
                if Color.is_brown(rgb):
                    tone = 1
                records.append({
                    "old_row": r,
                    "old_col": c,
                    "rgb": rgb,
                    'code': code,
                    "hue": h,
                    "light": l,
                    "saturation": s,
                    "tone": tone
                })

        # Sort first by hue (left to right), then by lightness (top to bottom)
        df_rgb = pd.DataFrame(records)
        df_code = pd.DataFrame()
        sorted_by_hue = df_rgb.sort_values(by=["tone", "hue"], ascending=[False, True]).reset_index(drop=True)
        df_rgb = pd.DataFrame(index=range(n_rows), columns=range(n_cols), dtype=object)

        # Split DataFrame into columns and convert back to DataFrame if needed
        indices = np.array_split(range(len(sorted_by_hue)), n_cols)
        for new_c, idx_group in enumerate(indices):
            col_group = sorted_by_hue.iloc[idx_group]
            # sort by light
            col_sorted = col_group.sort_values(by=["tone", "light", "code"], ascending=[False, False, True]).reset_index(drop=True)
            # fill
            for new_r in range(min(n_rows, len(col_sorted))):
                if self.sort_color:
                    df_rgb.iloc[new_r, new_c] =  col_sorted.loc[new_r]['rgb']
                    df_code.loc[new_r, new_c] =  col_sorted.loc[new_r]['code']
                else:
                    df_rgb.iloc[col_sorted.loc[new_r]['old_row'], col_sorted.loc[new_r]['old_col']] =  col_sorted.loc[new_r]['rgb']
                    df_code.loc[col_sorted.loc[new_r]['old_row'], col_sorted.loc[new_r]['old_col']] =  col_sorted.loc[new_r]['code']
        self.df_code = df_code
        self.df_rgb = df_rgb
        return df_rgb, df_code


    def _color_key(self) -> tuple:
        """Build a hashable key from current color configuration."""
        return tuple(
            (label, self.colors[label].td, self.colors[label].hex)
            for label in self.colors.get_labels()
        )

    def code_to_rgb(self, code: str):
        """
        Layered optical mixing using Beer-Lambert law.
        Results are LRU-cached keyed on (code, layer_height, color_config, alpha).
        """
        if not code or not code.strip():
            return (255, 255, 255)

        code = code.strip().upper()
        return _code_to_rgb_cached(code, self.layer_height, self._color_key(), self.alpha, self.blend_mode)


    def save_matrix_image(self, save_blank = True):
        rows, cols = self.df_code.shape
        cell_size = 50  # pixels per cell
        rgb_array = np.zeros((rows*cell_size, cols*cell_size, 3), dtype=np.uint8)
        for y in range(rows):
            for x in range(cols):
                rgb = self.df_rgb.iat[y, x]
                if rgb is None:
                    rgb_array[y*cell_size:(y+1)*cell_size, x*cell_size:(x+1)*cell_size] = (255, 255, 255)
                else:
                    rgb_array[y*cell_size:(y+1)*cell_size, x*cell_size:(x+1)*cell_size] = rgb

        file_path = os.path.join(self.directory, self.filename+'.png')
        os.makedirs(self.directory, exist_ok=True)
        img = Image.fromarray(rgb_array)
        draw = ImageDraw.Draw(img)
        img_blank = Image.fromarray(rgb_array)
        draw_blank = ImageDraw.Draw(img_blank)
        for y in range(rows):
            for x in range(cols):
                if self.df_code.iat[y, x] is None:
                    continue
                else:
                    if pd.isna(self.df_code.iat[y, x]):
                        continue
                    code = self.df_code.iat[y, x]
                    rgb = tuple(rgb_array[y*cell_size, x*cell_size])
                    rgb_blank = (255, 255, 255)
                    x0, y0 = x*cell_size, y*cell_size
                    x1, y1 = x0+cell_size, y0+cell_size
                    draw.rectangle([x0, y0, x1, y1], fill=rgb)
                    draw_blank.rectangle([x0, y0, x1, y1], fill=rgb_blank, outline=(0, 0, 0))
                    # Decide text color based on cell brightness
                    brightness = (rgb[0]*0.299 + rgb[1]*0.587 + rgb[2]*0.114)/255
                    text_color = (0,0,0) if brightness > 0.5 else (255,255,255)
                    draw.text((x0, y0), code, fill=text_color)
                    draw_blank.text((x0, y0), code, fill=(0, 0, 0))
        img.save(file_path)
        if save_blank:
            img_blank.save(f'{file_path[:-4]}_blank.png')


    def image_to_rgb_matrix(self, image_path, grid_size=16, sample_fraction=0.4, method='mean', save_samples=False):
        """
        rectangle of grid for calibration
        """
        img = Image.open(image_path).convert('RGB')
        w, h = img.size
        cell_w, cell_h = w / grid_size, h / grid_size
        arr = np.array(img)

        rgb_matrix = []
        for row in range(grid_size):
            row_colors = []
            for col in range(grid_size):
                # edge
                x0 = int(col * cell_w)
                x1 = int((col + 1) * cell_w)
                y0 = int(row * cell_h)
                y1 = int((row + 1) * cell_h)

                # shrink grid
                margin_x = int((1 - sample_fraction) * (x1 - x0) / 2)
                margin_y = int((1 - sample_fraction) * (y1 - y0) / 2)
                xs, xe = x0 + margin_x, x1 - margin_x
                ys, ye = y0 + margin_y, y1 - margin_y

                # sample
                patch = arr[ys:ye, xs:xe, :]
                if method == 'median':
                    color = tuple(np.median(patch.reshape(-1, 3), axis=0).astype(int))
                else:
                    color = tuple(np.mean(patch.reshape(-1, 3), axis=0).astype(int))
                row_colors.append(color)

                if save_samples:
                    filename = f"tile{row}_{col}.png"
                    directory = os.path.join(self.directory, 'samples')
                    file_path = os.path.join(directory, filename)
                    os.makedirs(directory, exist_ok=True)

                    # save and check cropped sample
                    cell = img.crop((xs, ys, xe, ye))
                    # Save cropped image
                    cell.save(file_path)
            rgb_matrix.append(row_colors)

        df = pd.DataFrame(rgb_matrix)
        return df

    def color_variance(self, df_ref, df_photo, new_df_rgb, new_df_code, save_comp_img = False):
        rows, cols = df_ref.shape
        if df_ref.shape != df_photo.shape:
            return

        code_color_map = self.matrix_to_code_color_map(new_df_rgb, new_df_code)

        diffs = np.zeros((rows, cols))
        max_diff = math.sqrt(255 ** 2 *3)

        for y_idx in range(df_ref.shape[0]):
            for x_idx in range(df_ref.shape[1]):
                photo_code = df_ref.iat[y_idx, x_idx][0]
                photo_rgb = df_photo.iat[y_idx, x_idx]
                new_rgb = code_color_map[photo_code]

                diff = math.sqrt((new_rgb[0]-photo_rgb[0]) ** 2 + (new_rgb[1]-photo_rgb[1]) ** 2 + (new_rgb[2]-photo_rgb[2]) ** 2) / max_diff
                diffs[y_idx, x_idx] = round(diff, 2)

        avg = np.average(pd.DataFrame(diffs))
        wrong_color_count = dict.fromkeys(self.colors.get_labels(), 0)
        for y_idx in range(df_ref.shape[0]):
            for x_idx in range(df_ref.shape[1]):
                if diffs[y_idx, x_idx] > avg:
                    code, _ = df_ref.iloc[y_idx][x_idx]
                    for c in code:
                        wrong_color_count[c] = wrong_color_count[c] + diffs[y_idx, x_idx]
        logger.debug("Wrong color count: %s", wrong_color_count)
        return avg


    def parse_cell(self,s):
        if pd.isna(s):
            return s
        if not isinstance(s, str):
            return s
        # remove np.float64(...) wrappers
        s2 = re.sub(r'np\.float64\(([^)]+)\)', r'\1', s)
        try:
            return ast.literal_eval(s2)   # yields ('CODE', (r, g, b))
        except Exception:
            return s2

if __name__ == "__main__":
    p1s_plate = 256, 228, 256
    a1_plate = 256, 256, 256
    four = BlendTestGenerator(
        colors=Colors(clear=False),
        same_height=True, sort_color=True, verbose=True,
        layer_height=0.08, layer_count_max=4)

    clear = BlendTestGenerator(
        colors=Colors(clear=True),
        layer_height=.28*3, layer_count_max=4,
        same_height=True, sort_color=True, verbose=False
        )
