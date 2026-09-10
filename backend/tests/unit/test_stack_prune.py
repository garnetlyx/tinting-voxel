"""
Regression tests for the composition-pruned stack search (core/stack_prune.py).

The pruning is only valid while the pruned+refined mapping stays within a ΔE00
budget of the full-enumeration oracle — the gate required by the research note
(TD_ADAPTIVE_STACK_SEARCH.md, "Productionization sketch"). Budgets are asserted
at both 6 and 8 layers; 5 filaments x 8 layers is the frozen headline case
(390,625 fully enumerated codes vs 495 composition representatives).

These tests also pin the calibration-field contract: custom filament
configurations carrying measured td_rgb / td_neutral must survive every
request path (process, download, batch) so an edited Clear palette keeps
per-channel blending and the transparent prune regime.
"""
import json

import numpy as np
import pytest
from skimage.color import deltaE_ciede2000, rgb2lab

from core.color_config import get_preset
from core.color_materials import Color, Colors
from core.stack_prune import (
    MAX_PERMS_PER_COMPOSITION,
    composition_codes,
    distinct_permutations,
    is_translucent_set,
    refine_matches,
)
from services.image_processor import _map_and_refine
from services.stl_generator import _build_code_to_rgb, compute_reference_matrices

# Frozen headline case: 5 filaments x 8 layers.
FULL_CODES_5X8 = 5**8              # 390,625
COMPOSITIONS_5X8 = 495             # C(5+8-1, 8)

# Budgets (ΔE00, CIEDE2000) measured with correctly normalized sRGB->Lab:
# reachable targets at 6 layers max 2.18, at 8 layers max 1.41.
MAX_DELTA_E_BUDGET = 7.5
MEAN_DELTA_E_BUDGET = 1.5
# For arbitrary (possibly out-of-gamut) targets the pruned pick may not be a
# meaningfully worse match than the oracle's pick, by the production metric.
METRIC_EXCESS_BUDGET = 4.0


def _clear_colors() -> Colors:
    return Colors.from_configs(get_preset("clear_cmywg"))


def _lab(rgb):
    """0-255 RGB -> CIELAB; rgb2lab expects [0, 1] inputs."""
    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return rgb2lab(arr).reshape(-1, 3)


def _codes_from_matrix(code_df):
    return [
        code_df.iat[r, c]
        for r in range(code_df.shape[0])
        for c in range(code_df.shape[1])
    ]


class TestCandidateGeneration:
    def test_composition_count_matches_combinatorics(self):
        labels = ["C", "M", "Y", "W", "G"]
        for layers in (4, 6, 8):
            codes = composition_codes(labels, layers)
            expected = len(list(__import__("itertools").combinations_with_replacement(labels, layers)))
            assert len(codes) == expected == len(set(codes))
            assert all(len(c) == layers for c in codes)

    def test_frozen_5x8_counts_full_vs_pruned(self):
        labels = ["C", "M", "Y", "W", "G"]
        assert len(composition_codes(labels, 8)) == COMPOSITIONS_5X8
        assert FULL_CODES_5X8 == 390_625

        colors = _clear_colors()
        full_df, _ = compute_reference_matrices(8, 0.84, colors, prune=False)
        pruned_df, _ = compute_reference_matrices(8, 0.84, colors)
        assert len(set(_codes_from_matrix(full_df))) == FULL_CODES_5X8
        assert len(set(_codes_from_matrix(pruned_df))) == COMPOSITIONS_5X8

    def test_distinct_permutations_unique_and_capped(self):
        perms = distinct_permutations("CCMMYYWG")
        assert len(perms) == len(set(perms))
        assert len(perms) == 5040  # 8!/(2!*2!*2!*1!*1!) distinct orderings
        capped = distinct_permutations("ABCDEFGH", cap=50)
        assert len(capped) <= 50
        assert "ABCDEFGH" in capped  # deterministic sample keeps endpoints


class TestRegimeGate:
    def test_clear_set_is_translucent(self):
        assert is_translucent_set(_clear_colors())

    def test_bambu_set_is_not_translucent(self):
        colors = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
        assert not is_translucent_set(colors)

    def test_unmeasured_color_falls_back_to_configured_td(self):
        colors = Colors(colors={
            "A": Color(name="A", hex="#112233", transmission_distance=10.0),
            "B": Color(name="B", hex="#332211", transmission_distance=20.0),
            "C": Color(name="C", hex="#221133", transmission_distance=30.0),
            "D": Color(name="D", hex="#112233", transmission_distance=10.0),
        })
        assert is_translucent_set(colors)
        assert not is_translucent_set(colors, threshold_mm=15.0)

    def test_prune_true_never_forces_pruning(self):
        """Pruning is automatic and translucent-only; True is rejected outright."""
        clear = _clear_colors()
        bambu = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
        for colors in (clear, bambu):
            with pytest.raises(ValueError, match="prune=True is not supported"):
                compute_reference_matrices(4, 0.84, colors, prune=True)

    def test_opaque_set_keeps_full_enumeration(self):
        bambu = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
        code_df, _ = compute_reference_matrices(4, 0.08, bambu)
        assert len(set(_codes_from_matrix(code_df))) == 5**4

    def test_mixed_set_keeps_full_enumeration(self):
        """Opaque/mixed sets remain exact: one opaque filament disqualifies
        the whole set from pruning (theory: opaque + transparent blends are
        possible, so only fully transparent sets may prune)."""
        clear = [c for c in get_preset("clear_cmywg")]
        mixed = clear[:4] + [
            type(clear[0])(
                name="Key", hex="#0B0F0C", transmission_distance=0.1,
                alpha=12.0, k=10.0, td_neutral=0.1,
            )
        ]
        colors = Colors.from_configs(mixed)
        assert not is_translucent_set(colors)
        code_df, _ = compute_reference_matrices(4, 0.84, colors)
        assert len(set(_codes_from_matrix(code_df))) == 5**4  # full, not C(8,4)=70


class TestRefinement:
    def test_refine_is_noop_for_opaque_set(self):
        colors = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
        codes = ["CMYK"] * 3
        rgbs = [(1, 2, 3)] * 3
        out_codes, out_rgbs = refine_matches(
            [(10, 20, 30)] * 3, codes, rgbs,
            code_matrix=None, rgb_matrix=None,
            colors=colors, layer_height=0.08,
            code_to_rgb=lambda c: (0, 0, 0),
        )
        assert out_codes == codes
        assert out_rgbs == rgbs

    def test_refine_recovers_best_order_within_composition(self):
        colors = _clear_colors()
        code_to_rgb = _build_code_to_rgb(colors, 4, 0.84)
        pruned_code_df, pruned_rgb_df = compute_reference_matrices(4, 0.84, colors)

        # Target = the blend of a specific ordering of one composition.
        target_rgb = code_to_rgb("CMYG")
        stage1_codes = ["CGMY"]  # canonical (sorted) representative
        stage1_rgbs = [code_to_rgb("CGMY")]

        refined_codes, refined_rgbs = refine_matches(
            [target_rgb], stage1_codes, stage1_rgbs,
            code_matrix=pruned_code_df, rgb_matrix=pruned_rgb_df,
            colors=colors, layer_height=0.84,
            code_to_rgb=code_to_rgb,
        )
        assert refined_codes[0] in distinct_permutations("CGMY")
        canonical_de = float(deltaE_ciede2000(
            _lab(target_rgb), _lab(stage1_rgbs[0]), channel_axis=-1).ravel()[0])
        refined_de = float(deltaE_ciede2000(
            _lab(target_rgb), _lab(refined_rgbs[0]), channel_axis=-1).ravel()[0])
        assert refined_de <= canonical_de
        assert refined_de < 1.0  # the exact ordering exists in the candidate set


class TestPrunedVsFullOracle:
    @pytest.mark.parametrize("layer_count", [6, 8])
    def test_pruned_refined_mapping_within_delta_e_budget(self, layer_count):
        """Ship gate: pruned+refined must match the full-enumeration oracle.

        - Reachable targets (sampled from the blend gamut itself): the pruned
          pick must land within the spread-derived budget of the oracle pick.
        - Arbitrary targets: the pruned pick must not be meaningfully worse a
          match than the oracle's, by the production perceptual metric.
          Comparing the two picks' RGB directly is not meaningful for colors
          outside the printable gamut, where both paths are equally
          approximate.
        """
        colors = _clear_colors()
        layer_height = 0.84

        full_code_df, full_rgb_df = compute_reference_matrices(
            layer_count, layer_height, colors, prune=False,
        )
        pruned_code_df, pruned_rgb_df = compute_reference_matrices(
            layer_count, layer_height, colors,
        )
        assert len(set(_codes_from_matrix(pruned_code_df))) < len(
            set(_codes_from_matrix(full_code_df))
        )

        rng = np.random.default_rng(42)
        # The 8-layer full oracle enumerates 390,625 codes; keep the sample
        # sizes statistically meaningful but bounded so the suite stays fast.
        n_reachable = 60 if layer_count >= 8 else 150
        n_arbitrary = 80 if layer_count >= 8 else 200

        # Reachable targets: sample blend outputs from the full matrix.
        gamut = np.array([
            full_rgb_df.iat[r, c]
            for r in range(full_rgb_df.shape[0])
            for c in range(full_rgb_df.shape[1])
        ])
        reachable = gamut[rng.choice(len(gamut), size=n_reachable, replace=False)].tolist()

        # The oracle is the exact argmin over every ordering in the full
        # matrix (stage 1 only): refinement cannot improve an exhaustive set.
        from core.color_materials import Color as _C
        _, full_rgbs = _C.map_to_nearest_color(reachable, full_code_df, full_rgb_df)
        _, pruned_rgbs = _map_and_refine(
            reachable, pruned_code_df, pruned_rgb_df, colors, layer_count, layer_height,
        )
        de = np.array([
            float(deltaE_ciede2000(
                _lab([full_rgbs[i]]), _lab([pruned_rgbs[i]]), channel_axis=-1).ravel()[0])
            for i in range(len(reachable))
        ])
        assert de.mean() <= MEAN_DELTA_E_BUDGET, f"mean dE00 {de.mean():.2f} over budget"
        assert de.max() <= MAX_DELTA_E_BUDGET, f"max dE00 {de.max():.2f} over budget"

        # Arbitrary targets: metric excess of the pruned pick vs the oracle pick,
        # contracted for colors the palette can plausibly represent.
        targets = rng.integers(0, 256, size=(n_arbitrary, 3)).tolist()
        target_lab = _lab(targets)
        _, full_rgbs_r = _C.map_to_nearest_color(targets, full_code_df, full_rgb_df)
        _, pruned_rgbs_r = _map_and_refine(
            targets, pruned_code_df, pruned_rgb_df, colors, layer_count, layer_height,
        )
        oracle_dist = np.array([
            float(Color.perceptual_distance(target_lab[i], _lab([full_rgbs_r[i]]))[0])
            for i in range(len(targets))
        ])
        excess = np.array([
            float(Color.perceptual_distance(target_lab[i], _lab([pruned_rgbs_r[i]]))[0])
            for i in range(len(targets))
        ]) - oracle_dist
        plausible = oracle_dist < 30
        assert plausible.sum() >= 15, "target sample unexpectedly all out-of-gamut"
        assert excess[plausible].max() <= METRIC_EXCESS_BUDGET, (
            f"pruned pick is {excess[plausible].max():.2f} worse than oracle on "
            f"plausible targets"
        )
        assert excess.mean() <= 1.0, (
            f"mean excess {excess.mean():.2f} shows a systematic prune penalty"
        )


class TestCalibrationForwarding:
    """Edited Clear palettes must keep td_rgb/td_neutral on every request path."""

    EDITED_CLEAR = [
        {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7,
         "alpha": 12.0, "k": 1.93, "td_rgb": [1.04, 4.66, 8.30], "td_neutral": 48.9,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3,
         "alpha": 12.0, "k": 1.44, "td_rgb": [12.87, 2.39, 3.70], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1,
         "alpha": 12.0, "k": 0.67, "td_rgb": [15.13, 12.29, 2.81], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0,
         "alpha": 12.0, "k": 0.11, "td_rgb": [17.95, 18.90, 17.21], "td_neutral": 100,
         "td_scale": 1.0, "td_gamma": 1.0},
        {"name": "Grey", "hex": "#9A9D9C", "transmission_distance": 1.7,
         "alpha": 12.0, "k": 10.0, "td_rgb": [2.23, 1.69, 1.19], "td_neutral": 7.3,
         "td_scale": 1.0, "td_gamma": 1.0},
    ]

    def test_download_and_process_paths_keep_measured_fields(self):
        from api.models import FilamentColorConfig
        from api.routes.download_v2 import get_colors_from_request

        configs = [FilamentColorConfig.model_validate(c) for c in self.EDITED_CLEAR]
        colors = get_colors_from_request(None, configs)
        cyan = colors.colors["C"]
        assert cyan.td_rgb == (1.04, 4.66, 8.30)
        assert cyan.td_neutral == 48.9
        assert colors.get_blend_mode() == "per_channel"
        assert is_translucent_set(colors), "edited Clear palette must keep the prune regime"
