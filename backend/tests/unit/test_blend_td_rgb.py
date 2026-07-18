"""Tests for the beer_lambert_td_rgb blend mode (Phase-8 per-channel TD)."""

import numpy as np
import pytest

from core.blend_models import _blend_by_mode, validate_blend_mode
from core.color_config import ColorConfig
from core.color_materials import Color


def _color(label, hex_val, td=10.0, td_rgb=None):
    return Color(label, td, hex=hex_val, td_rgb=td_rgb)


@pytest.fixture
def cyan_map():
    # Staircase-style measurement: cyan attenuates R fastest.
    return {
        "C": _color("C", "#4C72A0", td=2.0, td_rgb=(1.35, 2.54, 4.09)),
        "W": _color("W", "#D9D6C5", td=18.0, td_rgb=(17.9, 18.9, 17.2)),
        "G": _color("G", "#676563", td=7.3),  # scalar fallback, no td_rgb
        "Y": _color("Y", "#D8B695", td=15.0, td_rgb=(22.1, 15.4, 5.38)),
    }


class TestValidation:
    def test_mode_is_registered(self):
        assert validate_blend_mode("beer_lambert_td_rgb") == "beer_lambert_td_rgb"

    def test_color_config_accepts_td_rgb(self):
        cfg = ColorConfig(name="Cyan", hex="#4C72A0",
                          transmission_distance=2.0, td_rgb=(1.35, 2.54, 4.09))
        assert cfg.td_rgb == (1.35, 2.54, 4.09)

    def test_color_config_rejects_bad_td_rgb(self):
        with pytest.raises(ValueError):
            ColorConfig(name="Cyan", hex="#4C72A0",
                        transmission_distance=2.0, td_rgb=(1.0, 2.0))
        with pytest.raises(ValueError):
            ColorConfig(name="Cyan", hex="#4C72A0",
                        transmission_distance=2.0, td_rgb=(1.0, -2.0, 3.0))

    def test_color_rejects_bad_td_rgb(self):
        with pytest.raises(ValueError):
            Color("C", 2.0, hex="#4C72A0", td_rgb=(0.0, 1.0, 2.0))


class TestBlend:
    def test_empty_code_returns_white(self, cyan_map):
        rgb = _blend_by_mode("", 0.08, cyan_map,
                             blend_mode="beer_lambert_td_rgb")
        assert rgb == (255.0, 255.0, 255.0)

    def test_channel_selectivity_matches_td_ordering(self, cyan_map):
        # Cyan: td_R < td_G < td_B, so on white backing R is attenuated most.
        r, g, b = _blend_by_mode("CCCC", 0.08, cyan_map,
                                 blend_mode="beer_lambert_td_rgb")
        assert r < g < b

    def test_scalar_fallback_when_td_rgb_missing(self, cyan_map):
        # Grey has no td_rgb: transmission must be channel-neutral, so the
        # result interpolates between backing white and the filament color.
        r, g, b = _blend_by_mode("G", 0.08, cyan_map,
                                 blend_mode="beer_lambert_td_rgb")
        grey = cyan_map["G"]
        t = np.exp(-np.log(10) * 0.08 / 7.3)
        expected = np.array(grey.rgb) * (1 - t) + 255.0 * t
        assert np.allclose((r, g, b), expected, atol=1e-6)

    def test_thick_stack_approaches_filament_color(self, cyan_map):
        # Many layers: transmission -> 0, result -> nominal filament RGB.
        rgb = _blend_by_mode("C" * 40, 1.0, cyan_map,
                             blend_mode="beer_lambert_td_rgb")
        assert np.allclose(rgb, cyan_map["C"].rgb, atol=1.0)

    def test_thin_layer_close_to_backing(self, cyan_map):
        # Near-transparent clear filament, single thin layer on white.
        rgb = _blend_by_mode("W", 0.08, cyan_map,
                             blend_mode="beer_lambert_td_rgb")
        assert all(c > 245 for c in rgb)

    def test_monotonic_in_thickness(self, cyan_map):
        # More layers of yellow absorb more blue.
        blues = []
        for n in (1, 2, 4, 8):
            rgb = _blend_by_mode("Y" * n, 0.08, cyan_map,
                                 blend_mode="beer_lambert_td_rgb")
            blues.append(rgb[2])
        assert blues == sorted(blues, reverse=True)

    def test_black_backing(self, cyan_map):
        # On black backing a thin clear layer stays dark.
        rgb = _blend_by_mode("W", 0.08, cyan_map,
                             blend_mode="beer_lambert_td_rgb",
                             background_rgb=(0.0, 0.0, 0.0))
        assert all(c < 30 for c in rgb)

    def test_existing_modes_unaffected(self, cyan_map):
        # td_rgb colors pass through legacy modes without error.
        for mode in ("original", "kromacut", "per_channel", "hybrid"):
            rgb = _blend_by_mode("CY", 0.08, cyan_map, blend_mode=mode)
            assert len(rgb) == 3
