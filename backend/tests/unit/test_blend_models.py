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


class TestFrozenEquivalenceCertification:
    """Executable three-family equivalence proof (freeze-time certification).

    The unified formula must reproduce, at every code, the outputs of the
    retired per-family models at their deployed parameter points:

    - Bambu CMYWK/CMYW: retired hybrid_per_color_k_td1s_gamma,
      mu_ch = alpha_s/(ts*td_td1s**tg) + k_c*A_ch with the Phase-6 fitted
      values — the presets' folded tds must match exactly.
    - Clear mean-flat: retired beer_lambert_td_rgb under the production
      strip condition (scalar td broadcast, k_residual=0) — i.e. plain
      10^(-d/td), exactly what k=0 gives.
    - Default custom set: plain base-10 Beer-Lambert 10^(-d/td).
    """

    LN10 = float(np.log(10.0))

    def _retired_reference_blends(self, codes, layer_height, colors_spec):
        """Reference engine: mu_ch = scatter + k*A_ch with per-family scatter,
        composed via the light-loss allocation (paper Eqs. 4-8)."""
        out = []
        for code in codes:
            transmissions = []
            for ch in code:
                scatter, k, hexv = colors_spec[ch]
                h = hexv.lstrip('#')
                A = np.array([255 - int(h[i:i+2], 16) for i in (0, 2, 4)]) / 255.0
                mu = scatter + k * A
                transmissions.append(np.exp(-mu * layer_height))
            remain = np.ones(3)
            loss = []
            for t in transmissions:
                loss.append(remain * (1 - t)); remain = remain * t
            loss.append(remain)
            loss = np.array(loss)
            total = np.where(loss.sum(axis=0) > 0, loss.sum(axis=0), 1.0)
            loss /= total
            bw = loss[-1]
            rgb = np.ones(3)
            for i, ch in enumerate(code):
                h = colors_spec[ch][2].lstrip('#')
                A = np.array([255 - int(h[i:i+2], 16) for i in (0, 2, 4)]) / 255.0
                rgb -= A * loss[i]
            out.append(np.clip((bw + (1 - bw) * rgb) * 255, 0, 255))
        return out

    def test_bambu_cmywk_folded_matches_retired_fitted_model(self):
        from core.color_config import get_preset
        import itertools
        # Retired Phase-6 parameters (acda338): alpha_s=8.08, ts=1.48, tg=0.20
        # over TD1S readings; k fitted per color.
        td1s = {'C': 2.0, 'M': 2.9, 'Y': 5.0, 'W': 6.1, 'K': 0.1}
        kf = {'C': 8.13, 'M': 8.42, 'Y': 3.73, 'W': 12.39, 'K': 17.65}
        hexes = {'C': '#3D79C6', 'M': '#B3356E', 'Y': '#FFE665', 'W': '#FFFFFF', 'K': '#0B0F0C'}
        spec = {ch: (8.08 / (1.48 * td1s[ch] ** 0.20), kf[ch], hexes[ch]) for ch in td1s}

        colors = Colors.from_configs(get_preset('bambu_cmywk_phase6'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=6)
        codes = [''.join(p) for p in itertools.product('CMYWK', repeat=6)]
        reference = self._retired_reference_blends(codes, 0.08, spec)
        unified = gen.codes_to_rgb(codes)  # batch: every code, vectorized
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"bambu CMYWK folded equivalence broken over all {len(codes)} codes: {max_diff}"

    def test_bambu_cmyw_folded_matches_retired_fitted_model(self):
        from core.color_config import get_preset
        import itertools
        td1s = {'C': 2.0, 'M': 2.9, 'Y': 5.0, 'W': 6.1}
        kf = {'C': 8.13, 'M': 8.42, 'Y': 3.73, 'W': 12.39}
        hexes = {'C': '#3D79C6', 'M': '#B3356E', 'Y': '#FFE665', 'W': '#FFFFFF'}
        spec = {ch: (8.08 / (1.48 * td1s[ch] ** 0.20), kf[ch], hexes[ch]) for ch in td1s}

        colors = Colors.from_configs(get_preset('bambu_cmyw_phase6'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=6)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=6)]
        reference = self._retired_reference_blends(codes, 0.08, spec)
        unified = gen.codes_to_rgb(codes)  # batch: every code, vectorized
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"bambu CMYW folded equivalence broken over all {len(codes)} codes: {max_diff}"

    # Immutable production baseline (acda338 clear preset): hexes and tds
    # frozen at deploy time. The test fails if the shipped preset drifts
    # from this deployed behavior in ANY value.
    PROD_CLEAR = {
        'hexes': {'C': '#5489B4', 'M': '#DE5740', 'Y': '#DDC465', 'W': '#D9D6C5'},
        'means': {'C': 4.7, 'M': 6.3, 'Y': 10.1, 'W': 18.0},
    }

    def test_clear_mean_flat_is_plain_base10(self):
        from core.color_config import get_preset
        import itertools
        means = self.PROD_CLEAR['means']
        hexes = self.PROD_CLEAR['hexes']
        # Retired production behavior (strip condition): scalar td broadcast,
        # no k term — plain 10^(-d/td), at the frozen production hexes.
        spec = {ch: (self.LN10 / means[ch], 0.0, hexes[ch]) for ch in means}

        # The shipped preset must carry exactly these frozen values.
        preset = get_preset('clear_cmyw')
        for c in preset:
            assert c.hex == self.PROD_CLEAR['hexes'][c.name[0]], (
                f"clear hex drifted from frozen production value: {c.name} {c.hex}"
            )
            assert c.transmission_distance == self.PROD_CLEAR['means'][c.name[0]]

        colors = Colors.from_configs(get_preset('clear_cmyw'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.84, layer_count_max=4)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=4)]
        reference = self._retired_reference_blends(codes, 0.84, spec)
        unified = [gen.code_to_rgb(c) for c in codes]
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"clear mean-flat equivalence broken: {max_diff}"

    def test_default_custom_set_is_plain_base10(self):
        import itertools
        tds = {'C': 4.0, 'M': 5.0, 'Y': 8.0, 'W': 12.0}
        hexes = {'C': '#00FFFF', 'M': '#FF00FF', 'Y': '#FFFF00', 'W': '#FFFFFF'}
        spec = {ch: (self.LN10 / tds[ch], 0.0, hexes[ch]) for ch in tds}

        colors = Colors(colors={
            ch: Color(ch, tds[ch], hexes[ch]) for ch in tds
        })
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=4)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=4)]
        reference = self._retired_reference_blends(codes, 0.08, spec)
        unified = [gen.code_to_rgb(c) for c in codes]
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"default base-10 equivalence broken: {max_diff}"


class TestPresetShape:
    def test_clear_preset_is_four_color_cmyw(self):
        from core.color_config import get_preset
        preset = get_preset('clear_cmyw')
        assert [p.name[0] for p in preset] == ['C', 'M', 'Y', 'W']
        assert all(p.k == 0 for p in preset)
        assert [p.transmission_distance for p in preset] == [4.7, 6.3, 10.1, 18.0]
