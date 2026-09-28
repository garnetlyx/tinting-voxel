"""Map an image's white to print white, as the eye judges a scene by its white.

Photos rarely contain pure white: white objects come out as off-whites with a
slight cast. Matched as they are, off-whites land on tinted, darker stacks and
the print loses its whites. An image's white is the mean of its whitest pixels
(closest to white by CIEDE2000); when it is an off-white and the image has
contrast, colors are adapted from it to print white with the Bradford
transform. Low-contrast images keep their colors: their light tones are not
whites.
"""
from typing import Optional

import numpy as np
from skimage.color import deltaE_ciede2000, rgb2lab, rgb2xyz, xyz2lab, xyz2rgb

from config.settings import settings

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


def image_white(pixels: np.ndarray) -> Optional[np.ndarray]:
    """XYZ of an 8-bit RGB image's white, or None when colors should stay as they are.

    The white is the mean of the settings.white_point_share of pixels closest
    to white. It is kept when it lies within settings.white_point_max_delta_e
    of white and is at least settings.white_point_min_contrast times as bright
    as the darkest share of pixels.
    """
    rgb = pixels.reshape(-1, 3)
    rgb = rgb[::max(1, len(rgb) // LEVEL_SAMPLE)].reshape(-1, 1, 3) / 255.0
    xyz = rgb2xyz(rgb).reshape(-1, 3)
    distance = deltaE_ciede2000(rgb2lab(rgb).reshape(-1, 3), WHITE_LAB)
    count = max(1, round(len(xyz) * settings.white_point_share))
    white = xyz[np.argpartition(distance, count - 1)[:count]].mean(axis=0)
    dark = np.partition(xyz[:, 1], count - 1)[:count].mean()
    white_distance = deltaE_ciede2000(xyz2lab(white.reshape(1, 3)), WHITE_LAB)[0]
    if white_distance > settings.white_point_max_delta_e:
        return None
    if white[1] < settings.white_point_min_contrast * dark:
        return None
    return white


def adapt_to_white(rgb, white: np.ndarray) -> np.ndarray:
    """8-bit RGB colors (any shape ending in 3) adapted from `white` (XYZ) to print white."""
    rgb = np.asarray(rgb, dtype=np.uint8)
    gain = (BRADFORD @ PRINT_WHITE_XYZ) / (BRADFORD @ white)
    adaptation = np.linalg.inv(BRADFORD) @ np.diag(gain) @ BRADFORD
    adapted = xyz2rgb(rgb2xyz(rgb.reshape(-1, 1, 3) / 255.0) @ adaptation.T)
    return np.round(adapted * 255).astype(np.uint8).reshape(rgb.shape)


def adapt_to_image_white(pixels: np.ndarray, rgb) -> np.ndarray:
    """8-bit RGB colors as seen against the white of the image `pixels`
    (unchanged when image_white finds none)."""
    white = image_white(pixels)
    return np.asarray(rgb, dtype=np.uint8) if white is None else adapt_to_white(rgb, white)
