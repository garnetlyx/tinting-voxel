"""Colors print as seen against the image's white (core/white_point.py), while
the grouped colors stay the image's own."""
import base64
from io import BytesIO

import numpy as np
from PIL import Image
from skimage.color import rgb2xyz

from config.settings import settings
from core.blend_color import Colors
from core.color_config import get_preset
from core.white_point import adapt_to_white, image_white, seen_against
from services.image_processor import build_vector_simulated_preview, process_image
from services.param_search_service import Evaluator, FixedParams
from services.stl_generator import map_color_blocks_to_blend_results
from services.vector_processor import VectorProcessorConfig, process_image_vector_with_preview

BAMBU = Colors.from_configs(get_preset("bambu_cmyw"))
ALL_WHITE = "W" * 13  # 10 color layers and 3 backing layers
PRINT = dict(layer_count=10, layer_height=0.08, white_backing_layers=3, backing_filament="W")


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


def _decode(data_url: str) -> np.ndarray:
    return np.asarray(Image.open(BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("RGB"))


# Photo-like: the image's white is an off-white (#EAE6DA), next to a warm light
# grey (#CEC6B6), a near-black and a blue.
PHOTO = _bands(("EAE6DA", 5), ("CEC6B6", 20), ("20202A", 40), ("3050A0", 35))
# Pure white next to a pale green-grey (#D4DAC3), which matches a yellow-cyan
# stack by CIEDE2000, a near-black and a blue.
PALE = _bands(("FFFFFF", 10), ("D4DAC3", 20), ("20202A", 40), ("3050A0", 30))


def _process(pixels: np.ndarray) -> dict:
    return process_image(
        _png(pixels), max_colors=4, color_threshold=10, pixel_size=0.42, filament_colors=BAMBU, **PRINT,
    )


def _codes_at(result: dict, columns: list[int]) -> list[str]:
    """The printed stack of the block at each column."""
    codes = [mapped["code"] for mapped in result["mappedBlockColors"]]
    return [codes[result["labels"][0, column]] for column in columns]


def test_off_whites_print_white_against_the_image_white(monkeypatch):
    """Matched as it is, the warm light grey lands on colored layers; against
    the image's off-white it prints white like the off-white itself."""
    assert _codes_at(_process(PHOTO), [2, 10]) == [ALL_WHITE, ALL_WHITE]
    monkeypatch.setattr(settings, "low_contrast_shadow_lightness", 0.0)
    assert _codes_at(_process(PHOTO), [10]) != [ALL_WHITE]


def test_off_whites_print_white_rather_than_a_darker_tinted_stack(monkeypatch):
    assert _codes_at(_process(PALE), [15]) == [ALL_WHITE]
    monkeypatch.setattr(settings, "low_contrast_shadow_lightness", 0.0)
    assert _codes_at(_process(PALE), [15]) != [ALL_WHITE]


def test_grouped_colors_stay_the_images_own():
    result = _process(PHOTO)
    np.testing.assert_array_equal(_decode(result["segmentationImage"]), PHOTO)
    assert sorted(block["hex"] for block in result["colorBlocks"]) == ["#20202a", "#3050a0", "#cec6b6", "#eae6da"]
    assert sorted(entry["sourceHex"] for entry in result["mappedBlendPalette"]) == [
        "#20202A", "#3050A0", "#CEC6B6", "#EAE6DA",
    ]


def test_exports_print_against_the_white_processing_reports():
    result = _process(PALE)
    np.testing.assert_allclose(result["whitePoint"], image_white(PALE))
    blocks = result["colorBlocks"]
    codes, _ = map_color_blocks_to_blend_results(
        blocks, 0.08, 10, BAMBU, backing_layers=3, backing_filament="W", white_point=result["whitePoint"],
    )
    assert codes == [mapped["code"] for mapped in result["mappedBlockColors"]]
    codes_as_is, _ = map_color_blocks_to_blend_results(blocks, 0.08, 10, BAMBU, backing_layers=3, backing_filament="W")
    pale = result["labels"][0, 15]
    assert codes[pale] == ALL_WHITE and codes_as_is[pale] != ALL_WHITE


def test_only_off_whites_change_against_pure_white():
    seen = seen_against(PALE, image_white(PALE))
    assert np.all(seen[:, :30] == 255)
    np.testing.assert_array_equal(seen[:, 30:], PALE[:, 30:])


def test_the_image_white_becomes_print_white():
    assert adapt_to_white([0xEA, 0xE6, 0xDA], image_white(PHOTO)).tolist() == [255, 255, 255]


def test_the_white_is_the_mean_of_the_whitest_share(monkeypatch):
    monkeypatch.setattr(settings, "white_point_share", 0.05)
    pixels = _bands(("E8E8E8", 5), ("DDDDDD", 5), ("202020", 90))
    np.testing.assert_allclose(image_white(pixels), rgb2xyz(np.full((1, 1, 3), 0xE8 / 255)).reshape(3))


def test_muted_palettes_with_a_small_dark_accent_keep_their_colors():
    """A Morandi-like palette stays light across its darkest 5% even with a
    dark accent, so its light tones are the palette, not whites."""
    muted = _bands(("EDE0D7", 20), ("C9B8AE", 40), ("A89A92", 36), ("2A2622", 4))
    assert image_white(muted) is None
    assert _process(muted)["whitePoint"] is None


def test_low_contrast_images_and_images_without_an_off_white_have_no_white():
    assert image_white(_bands(("D8D4CC", 30), ("B0ACA6", 40), ("98948E", 30))) is None
    assert image_white(_bands(("F0D020", 30), ("B03020", 40), ("202020", 30))) is None
    np.testing.assert_array_equal(seen_against(PHOTO, None), PHOTO)
    assert _process(_bands(("D8D4CC", 30), ("B0ACA6", 40), ("98948E", 30)))["whitePoint"] is None


def test_svg_mode_keeps_its_colors_and_prints_off_whites_white():
    results, quantized = process_image_vector_with_preview(
        PHOTO, VectorProcessorConfig(epsilon=1.0, min_area=10, num_colors=4, pixel_size=0.42),
    )
    assert sorted(tuple(result["color"]) for result in results) == [
        (0x20, 0x20, 0x2A), (0x30, 0x50, 0xA0), (0xCE, 0xC6, 0xB6), (0xEA, 0xE6, 0xDA),
    ]
    preview = build_vector_simulated_preview(
        quantized, results, pixel_size=0.42, detail_size=None, colors=BAMBU,
        white_point=image_white(PHOTO), **PRINT,
    )
    codes = {entry["sourceHex"]: entry["code"] for entry in preview["mappedBlendPalette"]}
    assert codes["#EAE6DA"] == ALL_WHITE and codes["#CEC6B6"] == ALL_WHITE


def test_compared_settings_are_scored_against_the_image_white():
    fixed = FixedParams(layer_count=10, layer_height=0.08, pixel_size=0.42, white_backing_layers=3, detail_size=0.6)
    evaluator = Evaluator(_png(PHOTO), BAMBU, fixed)
    np.testing.assert_allclose(evaluator.white(), image_white(PHOTO))
    np.testing.assert_array_equal(evaluator.target(), seen_against(PHOTO, image_white(PHOTO)))
    assert evaluator.target()[0, 2].tolist() == [255, 255, 255]
