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

    def test_bambu_cmywk_folded_matches_paper_plate06_fit(self):
        from core.color_config import get_preset
        import itertools
        # Paper PLATE-06-H2C-A standard fit (IJAMT Table 3 / ESM Table S6;
        # research data/results/PLATE-06-H2C-paper-matrix/runs/A-standard/):
        # engine evaluates mu_ch = alpha_s/(1.48 * td_effective^0.20)
        # + k_c*A_ch (preset remap applied on top of the fitted remap).
        alpha_s = 2.2292
        td_eff = {'C': 5.3521, 'M': 5.6876, 'Y': 6.2178, 'W': 6.4235, 'K': 3.2781}
        kf = {'C': 3.4996, 'M': 4.3077, 'Y': 3.6572, 'W': 6.3168, 'K': 23.1863}
        hexes = {'C': '#3D79C6', 'M': '#B3356E', 'Y': '#FFE665', 'W': '#FFFFFF', 'K': '#0B0F0C'}
        spec = {ch: (alpha_s / (1.48 * td_eff[ch] ** 0.20), kf[ch], hexes[ch]) for ch in td_eff}

        colors = Colors.from_configs(get_preset('bambu_cmywk_phase6'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=6)
        codes = [''.join(p) for p in itertools.product('CMYWK', repeat=6)]
        reference = self._retired_reference_blends(codes, 0.08, spec)
        unified = gen.codes_to_rgb(codes)  # batch: every code, vectorized
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"bambu CMYWK folded equivalence broken over all {len(codes)} codes: {max_diff}"

    def test_bambu_cmyw_folded_matches_paper_plate06_fit(self):
        from core.color_config import get_preset
        import itertools
        alpha_s = 2.2292
        td_eff = {'C': 5.3521, 'M': 5.6876, 'Y': 6.2178, 'W': 6.4235}
        kf = {'C': 3.4996, 'M': 4.3077, 'Y': 3.6572, 'W': 6.3168}
        hexes = {'C': '#3D79C6', 'M': '#B3356E', 'Y': '#FFE665', 'W': '#FFFFFF'}
        spec = {ch: (alpha_s / (1.48 * td_eff[ch] ** 0.20), kf[ch], hexes[ch]) for ch in td_eff}

        colors = Colors.from_configs(get_preset('bambu_cmyw_phase6'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.08, layer_count_max=6)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=6)]
        reference = self._retired_reference_blends(codes, 0.08, spec)
        unified = gen.codes_to_rgb(codes)  # batch: every code, vectorized
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"bambu CMYW folded equivalence broken over all {len(codes)} codes: {max_diff}"

    # Paper transparent-track baseline (P08-kxa, PLATE-08-KX-A staircase
    # characterization): per-channel staircase TDs, k=0 — the unified
    # formula with td_rgb IS plain per-channel base-10 Beer-Lambert. The
    # test fails if the shipped preset drifts from this paper data in ANY
    # value.
    PAPER_CLEAR_CMYW = {
        'hexes': {'C': '#4C72A0', 'M': '#CE5E53', 'Y': '#D8B695', 'W': '#D9D6C5'},
        'td_rgb': {
            'C': (1.3490352079515975, 2.5371501740106988, 4.088658622221301),
            'M': (11.210903332862577, 2.0338821311932, 2.511508291542347),
            'Y': (22.124563670499846, 15.378730904545765, 5.384295692169828),
            'W': (17.949461574719358, 18.902845340687115, 17.207703003749966),
        },
    }

    def test_clear_per_channel_is_plain_base10(self):
        from core.color_config import get_preset
        import itertools
        td_rgb = self.PAPER_CLEAR_CMYW['td_rgb']
        hexes = self.PAPER_CLEAR_CMYW['hexes']
        # Reference: per-channel staircase TDs, no k term — mu_ch = ln10/td_ch.
        spec = {ch: (self.LN10 / np.array(td_rgb[ch]), 0.0, hexes[ch]) for ch in td_rgb}

        # The shipped preset must carry exactly these paper values.
        preset = get_preset('clear_cmyw')
        for c in preset:
            assert c.hex == self.PAPER_CLEAR_CMYW['hexes'][c.name[0]], (
                f"clear hex drifted from paper P08-kxa value: {c.name} {c.hex}"
            )
            assert tuple(c.td_rgb) == tuple(self.PAPER_CLEAR_CMYW['td_rgb'][c.name[0]]), (
                f"clear td_rgb drifted from paper P08-kxa value: {c.name} {c.td_rgb}"
            )

        colors = Colors.from_configs(get_preset('clear_cmyw'))
        gen = BlendTestGenerator(colors=colors, layer_height=0.84, layer_count_max=4)
        codes = [''.join(p) for p in itertools.product('CMYW', repeat=4)]
        reference = self._retired_reference_blends(codes, 0.84, spec)
        unified = [gen.code_to_rgb(c) for c in codes]
        max_diff = np.abs(np.array(reference) - np.array(unified)).max()
        assert max_diff < 1e-9, f"clear per-channel equivalence broken: {max_diff}"

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
    def test_bambu_presets_match_paper_plate06_fit(self):
        from core.color_config import get_preset
        preset = get_preset('bambu_cmywk_phase6')
        assert [p.name[0] for p in preset] == ['C', 'M', 'Y', 'W', 'K']
        assert [p.transmission_distance for p in preset] == [
            2.1381256008389844, 2.16428365111357, 2.203209113788528,
            2.217597459508237, 1.9384419920975642,
        ]
        assert [p.k for p in preset] == [3.4996, 4.3077, 3.6572, 6.3168, 23.1863]
        assert all(p.td_rgb is None for p in preset)

    def test_clear_cmyw_preset_is_paper_p08_kxa(self):
        from core.color_config import get_preset
        preset = get_preset('clear_cmyw')
        assert [p.name[0] for p in preset] == ['C', 'M', 'Y', 'W']
        assert all(p.k == 0 for p in preset)
        assert all(p.td_rgb is not None and len(p.td_rgb) == 3 for p in preset)
        # scalar td stays the channel arithmetic mean (display/fallback).
        for p in preset:
            assert p.transmission_distance == pytest.approx(sum(p.td_rgb) / 3.0)

    def test_clear_cmyg_preset_is_paper_p07_def(self):
        from core.color_config import get_preset
        preset = get_preset('clear_cmyg')
        assert [p.name[0] for p in preset] == ['C', 'M', 'Y', 'G']
        assert [p.hex for p in preset] == ['#5489B4', '#DE5740', '#DDC465', '#9A9D9C']
        assert all(p.k == 0 for p in preset)
        assert all(p.td_rgb is not None and len(p.td_rgb) == 3 for p in preset)
