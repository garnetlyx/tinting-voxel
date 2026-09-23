"""The sole production transmission model, its cache, and batch evaluator."""
import itertools
from dataclasses import asdict

import numpy as np
import pytest

from core.blend_color import BlendTestGenerator, Color, Colors, colors_key
from core.blend_models import _blend_unified, codes_to_rgb_batch, clear_rgb_cache, rgb_cache_info
from core.color_config import ColorConfig, PRESETS


@pytest.mark.parametrize("td", [2.0, (1.0, 2.0, 4.0)])
def test_one_decade_transmission(td):
    color = Color("C", td, "#00FFFF")
    assert color.transmission(1.0) == pytest.approx(
        np.power(10.0, -1.0 / np.asarray(color.td_channels))
    )
    assert Color("C", 1.0, hex="#00FFFF").transmission(1.0) == pytest.approx((.1, .1, .1))


@pytest.mark.parametrize("td", [0, -1, float("nan"), float("inf"), True,
                                   [1, 2], [1, 0, 3], [1, float("nan"), 3], "3"])
def test_invalid_td_is_rejected(td):
    with pytest.raises(ValueError):
        ColorConfig("Cyan", "#00FFFF", td)
    with pytest.raises(ValueError):
        Color("C", td, hex="#00FFFF")


def test_channel_list_is_canonicalized_without_another_td_field():
    config = ColorConfig("Cyan", "#00FFFF", [1, 2, 3])
    assert config.transmission_distance == (1.0, 2.0, 3.0)
    assert asdict(config) == {
        "name": "Cyan", "hex": "#00FFFF", "transmission_distance": (1.0, 2.0, 3.0),
    }


def test_single_layer_allocation_matches_hand_calculation():
    color = Color("C", 1.0, "#00FFFF")
    assert _blend_unified("C", 1.0, {"C": color}) == pytest.approx((48.45, 255, 255))
    assert _blend_unified("C", 1.0, {"C": color}, (0, 0, 0)) == pytest.approx((22.95, 229.5, 229.5))


def test_scalar_and_equal_channels_are_the_same_material():
    scalar = Colors(colors={"C": Color("C", 2.0, hex="#00FFFF")})
    channels = Colors(colors={"C": Color("C", (2, 2, 2), hex="#00FFFF")})
    assert colors_key(scalar) == colors_key(channels)
    assert BlendTestGenerator(colors=scalar).code_to_rgb("CCCC") == BlendTestGenerator(colors=channels).code_to_rgb("CCCC")


def test_editing_a_channel_invalidates_the_cached_prediction():
    colors = Colors(colors={"C": Color("C", (1, 2, 3), hex="#00FFFF")})
    gen = BlendTestGenerator(colors=colors)
    clear_rgb_cache()
    before = gen.code_to_rgb("CCCC")
    gen.code_to_rgb("CCCC")
    assert rgb_cache_info().hits == 1
    colors.colors["C"] = Color("C", (3, 2, 1), hex="#00FFFF")
    after = gen.code_to_rgb("CCCC")
    assert before != after
    assert rgb_cache_info().misses == 2


@pytest.mark.parametrize("preset", list(PRESETS))
@pytest.mark.parametrize("background", [None, (0, 0, 0), (120, 125, 130)])
def test_batch_matches_single_stack_for_every_preset(preset, background):
    colors = Colors.from_configs(PRESETS[preset])
    codes = ["".join(code) for code in itertools.product(colors.get_labels(), repeat=4)]
    for height in (.08, .84):
        batch = codes_to_rgb_batch(codes, height, colors_key(colors), background, chunk_size=97)
        individual = [_blend_unified(code, height, colors.colors, background) for code in codes]
        np.testing.assert_allclose(batch, individual, rtol=0, atol=1e-12)


def test_nearest_color_has_no_white_layer_quota():
    import pandas as pd
    codes = pd.DataFrame([["CCCC", "WWWW"]])
    rgbs = pd.DataFrame([[(252, 252, 252), (200, 200, 200)]])
    selected, _ = Color.map_to_nearest_color([(252, 252, 252)], codes, rgbs)
    assert selected == ["CCCC"]
