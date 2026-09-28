"""Colors are matched as seen against the image's white (core/white_point.py)."""
import math
from io import BytesIO

import numpy as np
from PIL import Image
from skimage.color import rgb2xyz

from config.settings import settings
from core.blend_color import Colors
from core.color_config import get_preset
from core.white_point import adapt_to_image_white, adapt_to_white, image_white
from services.image_processor import process_image
from services.param_search_service import Evaluator, FixedParams
from services.vector_processor import VectorProcessorConfig, process_image_vector_with_preview

BAMBU = Colors.from_configs(get_preset("bambu_cmyw"))
ALL_WHITE = "W" * 13  # 10 color layers and 3 backing layers


def _bands(*bands: tuple[str, int]) -> np.ndarray:
    """A 60-row RGB image of vertical bands, given as (hex color, width) pairs."""
    return np.concatenate([
        np.tile(np.frombuffer(bytes.fromhex(color), dtype=np.uint8), (60, width, 1))
        for color, width in bands
    ], axis=1)


def _png(pixels: np.ndarray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()


# Photo-like: the image's white is an off-white (#EAE6DA), next to a warm light
# grey (#CEC6B6), a near-black and a blue.
PHOTO = _bands(("EAE6DA", 5), ("CEC6B6", 20), ("20202A", 40), ("3050A0", 35))


def _codes_at(pixels: np.ndarray, columns: list[int]) -> list[str]:
    """The printed stack of the block at each column of a Bambu CMYW print."""
    result = process_image(
        _png(pixels), max_colors=4, color_threshold=10, pixel_size=0.42, filament_colors=BAMBU,
        layer_count=10, layer_height=0.08, white_backing_layers=3, backing_filament="W",
    )
    codes = [mapped["code"] for mapped in result["mappedBlockColors"]]
    return [codes[result["labels"][0, column]] for column in columns]


def test_off_whites_print_white_against_the_image_white(monkeypatch):
    """Matched as it is, the warm light grey lands on colored layers; against
    the image's off-white it prints white like the off-white itself."""
    assert _codes_at(PHOTO, [2, 10]) == [ALL_WHITE, ALL_WHITE]
    monkeypatch.setattr(settings, "white_point_min_contrast", math.inf)
    assert _codes_at(PHOTO, [10]) != [ALL_WHITE]


def test_the_image_white_becomes_print_white():
    assert adapt_to_white([0xEA, 0xE6, 0xDA], image_white(PHOTO)).tolist() == [255, 255, 255]


def test_the_white_is_the_mean_of_the_whitest_share(monkeypatch):
    monkeypatch.setattr(settings, "white_point_share", 0.05)
    pixels = _bands(("E8E8E8", 5), ("DDDDDD", 5), ("202020", 90))
    np.testing.assert_allclose(image_white(pixels), rgb2xyz(np.full((1, 1, 3), 0xE8 / 255)).reshape(3))


def test_low_contrast_images_keep_their_colors():
    hazy = _bands(("D8D4CC", 30), ("B0ACA6", 40), ("98948E", 30))
    assert image_white(hazy) is None
    np.testing.assert_array_equal(adapt_to_image_white(hazy, hazy), hazy)


def test_images_without_an_off_white_keep_their_colors():
    assert image_white(_bands(("F0D020", 30), ("B03020", 40), ("202020", 30))) is None


def test_pure_white_is_already_print_white():
    pixels = _bands(("FFFFFF", 10), ("CEC6B6", 20), ("20202A", 70))
    np.testing.assert_array_equal(adapt_to_image_white(pixels, pixels), pixels)


def test_svg_mode_sees_colors_against_the_image_white():
    results, quantized = process_image_vector_with_preview(
        PHOTO, VectorProcessorConfig(epsilon=1.0, min_area=10, num_colors=4, pixel_size=0.42),
    )
    assert (255, 255, 255) in [tuple(result["color"]) for result in results]
    assert quantized[0, 2].tolist() == [255, 255, 255]


def test_compared_settings_are_scored_against_the_image_white():
    fixed = FixedParams(layer_count=10, layer_height=0.08, pixel_size=0.42, white_backing_layers=3, detail_size=0.6)
    target = Evaluator(_png(PHOTO), BAMBU, fixed).target()
    np.testing.assert_array_equal(target, adapt_to_image_white(PHOTO, PHOTO))
    assert target[0, 2].tolist() == [255, 255, 255]
