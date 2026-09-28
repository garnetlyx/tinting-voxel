"""See an image's colors against its white, as the eye sees a scene.

Photos rarely contain pure white: white objects come out as off-whites with a
slight cast. Matched as they are, off-whites land on tinted, darker stacks,
and the print loses its whites and its contrast. An image's white is the mean
of its whitest pixels (closest to white by CIEDE2000). When it is an off-white
and the image reaches deep shadows, colors are matched to print stacks as seen
against it: adapted from it to print white with the Bradford transform, with
every color that is then an off-white matched as white. The extracted colors
themselves stay as they are. Low-contrast images, whose shadows stay light
(faded, high-key or Morandi palettes), keep their colors: their light tones
are the palette, not whites.
"""
from typing import Optional

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab, rgb2xyz, xyz2rgb

from config.settings import settings
from core.color_materials import DISTANCE_CHUNK

# Bradford cone-response matrix, the chromatic adaptation transform of ICC profiles.
BRADFORD = np.array([
    [0.8951, 0.2664, -0.1614],
    [-0.7502, 1.7135, 0.0367],
    [0.0389, -0.0685, 1.0296],
])
# Print white: sRGB white (D65, Y = 1) in XYZ.
PRINT_WHITE_XYZ = rgb2xyz(np.ones((1, 1, 3))).reshape(3)
WHITE_LAB = np.array([[100.0, 0.0, 0.0]])
# Pixels sampled to find an image's white and dark levels.
LEVEL_SAMPLE = 100_000


def _distance_to_white(rgb: np.ndarray) -> np.ndarray:
    """CIEDE2000 from white of 8-bit RGB colors, shape (n, 3)."""
    distance = np.empty(len(rgb))
    for start in range(0, len(rgb), DISTANCE_CHUNK):
        lab = rgb2lab(rgb[start:start + DISTANCE_CHUNK].reshape(-1, 1, 3) / 255.0).reshape(-1, 3)
        distance[start:start + DISTANCE_CHUNK] = deltaE_ciede2000(lab, WHITE_LAB)
    return distance


def image_white(pixels: np.ndarray) -> Optional[np.ndarray]:
    """XYZ of an 8-bit RGB image's white, or None when colors should stay as they are.

    The white is the mean of the settings.white_point_share of pixels closest
    to white. It is kept when it is an off-white (within
    settings.off_white_max_delta_e of white) and the image reaches deep
    shadows: its darkest settings.low_contrast_shadow_share of pixels are
    darker than L* settings.low_contrast_shadow_lightness.
    """
    rgb = pixels.reshape(-1, 3)
    rgb = rgb[::max(1, len(rgb) // LEVEL_SAMPLE)]
    shadows = np.percentile(rgb2lab(rgb.reshape(-1, 1, 3) / 255.0)[..., 0], 100 * settings.low_contrast_shadow_share)
    if shadows > settings.low_contrast_shadow_lightness:
        return None
    xyz = rgb2xyz(rgb.reshape(-1, 1, 3) / 255.0).reshape(-1, 3)
    count = max(1, round(len(rgb) * settings.white_point_share))
    whitest = np.argpartition(_distance_to_white(rgb), count - 1)[:count]
    white = xyz[whitest].mean(axis=0)
    white_rgb = np.round(xyz2rgb(white.reshape(1, 1, 3)) * 255).reshape(1, 3)
    if _distance_to_white(white_rgb)[0] > settings.off_white_max_delta_e:
        return None
    return white


def adapt_to_white(rgb, white: np.ndarray) -> np.ndarray:
    """8-bit RGB colors (any shape ending in 3) adapted from `white` (XYZ) to print white."""
    rgb = np.asarray(rgb, dtype=np.uint8)
    gain = (BRADFORD @ PRINT_WHITE_XYZ) / (BRADFORD @ white)
    adaptation = np.linalg.inv(BRADFORD) @ np.diag(gain) @ BRADFORD
    adapted = xyz2rgb(rgb2xyz(rgb.reshape(-1, 1, 3) / 255.0) @ adaptation.T)
    return np.round(adapted * 255).astype(np.uint8).reshape(rgb.shape)


def seen_against(rgb, white) -> np.ndarray:
    """8-bit RGB colors (any shape ending in 3) as seen against an image's white.

    `white` is the XYZ image_white found; colors are adapted from it to print
    white and off-whites become white. With no white (None) they are unchanged.
    """
    rgb = np.asarray(rgb, dtype=np.uint8)
    if white is None:
        return rgb
    adapted = adapt_to_white(rgb, np.asarray(white, dtype=np.float64))
    flat = adapted.reshape(-1, 3)
    flat[_distance_to_white(flat) <= settings.off_white_max_delta_e] = 255
    return adapted
