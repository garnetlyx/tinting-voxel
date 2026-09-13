"""
Tests for the unified blend model (core/blend_models.py).

One formula: mu_ch = ln10/td + k*A_ch, t_ch = exp(-mu*d), light-loss
allocation compose. No modes, no dispatch.
"""
import itertools

import numpy as np
import pytest

from core.blend_color import BlendTestGenerator, Color, Colors
from core.blend_models import (
    _blend_unified,
    _resolve_extinction,
    codes_to_rgb_batch,
)


class TestExtinction:
    def test_plain_beer_lambert_at_k0(self):
        c = Color('C', 2.0, '#FFFFFF', k=0)
        mu = _resolve_extinction(c)
        assert np.allclose(mu, np.log(10) / 2.0)

    def test_k_adds_hex_selectivity(self):
        # Pure cyan hex absorbs only red (A = (1, 0, 0)).
        c = Color('C', 10.0, '#00FFFF', k=5.0)
        mu = _resolve_extinction(c)
        assert mu[0] > mu[1] == mu[2]
        assert np.allclose(mu, np.log(10) / 10.0 + 5.0 * c.get_absorption())

    def test_zero_td_fully_opaque(self):
        c = Color('K', 0.0, '#000000')
        assert np.isinf(_resolve_extinction(c)).all()


class TestUnifiedBlend:
    def test_single_layer_matches_base10(self):
        c = Color('C', 1.0, '#00FFFF', k=0)
        rgb = _blend_unified('C', 1.0, {'C': c})
        # t = 10^(-1/1) = 0.1: 10% light reaches backing; cyan absorbs red.
        expected = 0.1 * 1.0 + 0.9 * (1 - (1 - 0x00 / 255) * 0.9)
        assert rgb[0] == pytest.approx(expected * 255, abs=1e-6)

    def test_opaque_white_stays_white(self):
        w = Color('W', 0.6, '#FFFFFF', k=12.39)
        rgb = _blend_unified('WWWWWWWW', 0.08, {'W': w})
        assert tuple(rgb) == pytest.approx((255.0, 255.0, 255.0), abs=1e-6)

    def test_transparent_white_passes_backing(self):
        w = Color('W', 15.0, '#FFFFFF', k=0)
        rgb = _blend_unified('WWWWWWWW', 0.08, {'W': w})
        assert tuple(rgb) == pytest.approx((255.0, 255.0, 255.0), abs=1e-6)

    def test_empty_code_is_white(self):
        assert _blend_unified('', 0.08, {}) == (255.0, 255.0, 255.0)


class TestBatchEquivalence:
    def test_batch_equals_per_code(self):
        colors = Colors(colors={
            l: Color(l, td, h, k=k)
            for l, h, td, k in zip(
                'CMYW',
                ['#3D79C6', '#B3356E', '#FFE665', '#FFFFFF'],
                [0.48, 0.52, 0.58, 0.61],
                [8.13, 8.42, 3.73, 12.39],
            )
        })
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=6)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=6)]
        batched = codes_to_rgb_batch(codes, 0.08, gen._color_key())
        per = [gen.code_to_rgb(c) for c in codes[:2000]]
        assert np.abs(np.array(batched[:2000]) - np.array(per)).max() < 1e-9


class TestPresetEquivalence:
    """The folded bambu values must reproduce the deployed behavior."""

    def test_bambu_folded_matches_reference(self):
        # Reference computed from the retired fitted model:
        # mu = 8.08 / (1.48 * td_td1s**0.2) + k * A_ch, verified bit-identical
        # against acda338 at freeze time (max diff 0.00 over 4000 codes).
        from core.color_config import get_preset
        colors = Colors.from_configs(get_preset('bambu_cmywk_phase6'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=4)
        c = colors['C']
        import math
        mu_ref = 8.08 / (1.48 * 2.0 ** 0.2) + 8.13 * c.get_absorption()
        t_ref = [math.exp(-m * 0.08) for m in mu_ref]
        # per-channel transmission drives the compose; check via extinction
        assert np.allclose(_resolve_extinction(c), mu_ref, rtol=1e-12)

    def test_clear_preset_is_four_color_cmyw(self):
        from core.color_config import get_preset
        preset = get_preset('clear_cmyw')
        assert [p.name[0] for p in preset] == ['C', 'M', 'Y', 'W']
        assert all(p.k == 0 for p in preset)
        assert [p.transmission_distance for p in preset] == [4.7, 6.3, 10.1, 18.0]
