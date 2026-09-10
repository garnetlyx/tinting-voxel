"""
Regression tests for the composition-pruned stack search (core/stack_prune.py).

The pruning is only valid while the pruned+refined mapping stays within a ΔE00
budget of the full-enumeration oracle — the gate required by the research note
(docs/TD_ADAPTIVE_STACK_SEARCH.md, "Productionization sketch"). The budget is
set from the measured intra-composition order spread of the staircase-calibrated
clear set (mean ~3, max ~6.4 ΔE00 at 8 layers), which bounds the worst case of
a mis-ranked composition.
"""
import itertools

import numpy as np
import pytest
from skimage.color import deltaE_ciede2000

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

# Measured intra-composition order spread bounds (clear set, 8 layers @ 0.84mm):
# mean 2.95 / p95 5.58 / max 6.37 dE00. The pruned+refined path may only lose
# to the full oracle by a mis-ranked composition, so the budget sits at the
# measured max plus a small safety margin.
MAX_DELTA_E_BUDGET = 7.5
MEAN_DELTA_E_BUDGET = 1.5
# For arbitrary (possibly out-of-gamut) targets the pruned pick may not be a
# meaningfully worse match than the oracle's pick, by the production metric.
METRIC_EXCESS_BUDGET = 2.0


def _clear_colors() -> Colors:
    return Colors.from_configs(get_preset("clear_cmywg"))


def _lab(rgb):
    from skimage.color import rgb2lab

    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return rgb2lab(arr).reshape(-1, 3)


class TestCandidateGeneration:
    def test_composition_count_matches_combinatorics(self):
        labels = ["C", "M", "Y", "W", "G"]
        for layers in (4, 6, 8):
            codes = composition_codes(labels, layers)
            expected = len(list(itertools.combinations_with_replacement(labels, layers)))
            assert len(codes) == expected
            assert len(set(codes)) == len(codes)  # unique
            assert all(len(c) == layers for c in codes)

    def test_clear_5x8_shrinks_790x(self):
        codes = composition_codes(["C", "M", "Y", "W", "G"], 8)
        assert len(codes) == 495
        assert 5**8 / len(codes) > 700

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
        # Fallback tds clear 6.7 -> translucent.
        assert is_translucent_set(colors)
        # ...but not a higher threshold.
        assert not is_translucent_set(colors, threshold_mm=15.0)

    def test_threshold_from_settings_can_be_overridden(self):
        assert is_translucent_set(_clear_colors(), threshold_mm=7.3)  # grey at 7.3
        assert not is_translucent_set(_clear_colors(), threshold_mm=7.4)


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

        pruned_code_df, pruned_rgb_df = compute_reference_matrices(
            4, 0.84, colors, prune=True,
        )

        # Target = the blend of a specific ordering of one composition.
        target_code = "CMYG"
        target_rgb = code_to_rgb(target_code)
        stage1_codes = ["CGMY"]  # canonical (sorted) representative
        stage1_rgbs = [code_to_rgb("CGMY")]

        refined_codes, refined_rgbs = refine_matches(
            [target_rgb], stage1_codes, stage1_rgbs,
            code_matrix=pruned_code_df, rgb_matrix=pruned_rgb_df,
            colors=colors, layer_height=0.84,
            code_to_rgb=code_to_rgb,
        )
        assert refined_codes[0] in distinct_permutations("CGMY")
        # The refined ordering must beat the canonical representative.
        canonical_de = float(deltaE_ciede2000(_lab(target_rgb), _lab(stage1_rgbs[0]), channel_axis=-1))
        refined_de = float(deltaE_ciede2000(_lab(target_rgb), _lab(refined_rgbs[0]), channel_axis=-1))
        assert refined_de <= canonical_de
        assert refined_de < 1.0  # the exact ordering exists in the candidate set


class TestPrunedVsFullOracle:
    def test_pruned_refined_mapping_within_delta_e_budget(self):
        """The ship gate: pruned+refined must match the full-enumeration oracle.

        Two budgets, per the research note's productionization sketch:
        - Reachable targets (sampled from the blend gamut itself): the pruned
          pick's RGB must land within the intra-composition order-spread bound
          of the oracle pick's RGB.
        - Arbitrary targets: the pruned pick must not be meaningfully worse a
          match than the oracle's, measured by the production perceptual
          metric. Comparing the two picks' RGB directly is not meaningful for
          colors outside the printable gamut, where both paths are equally
          approximate.
        """
        colors = _clear_colors()
        layer_count, layer_height = 6, 0.84

        full_code_df, full_rgb_df = compute_reference_matrices(
            layer_count, layer_height, colors, prune=False,
        )
        pruned_code_df, pruned_rgb_df = compute_reference_matrices(
            layer_count, layer_height, colors, prune=True,
        )
        assert len(pruned_code_df) < len(full_code_df)  # 210 comps vs 15625 codes

        rng = np.random.default_rng(42)

        # Reachable targets: sample blend outputs from the full matrix.
        gamut = np.array([
            full_rgb_df.iat[r, c]
            for r in range(full_rgb_df.shape[0])
            for c in range(full_rgb_df.shape[1])
        ])
        reachable = gamut[rng.choice(len(gamut), size=150, replace=False)].tolist()

        full_codes, full_rgbs = _map_and_refine(
            reachable, full_code_df, full_rgb_df, colors, layer_count, layer_height,
        )
        pruned_codes, pruned_rgbs = _map_and_refine(
            reachable, pruned_code_df, pruned_rgb_df, colors, layer_count, layer_height,
        )

        de = np.asarray(deltaE_ciede2000(
            _lab(full_rgbs).reshape(-1, 1, 3),
            _lab(pruned_rgbs).reshape(-1, 1, 3),
            channel_axis=-1,
        )).reshape(-1)
        assert de.mean() <= MEAN_DELTA_E_BUDGET, f"mean dE00 {de.mean():.2f} over budget"
        assert de.max() <= MAX_DELTA_E_BUDGET, f"max dE00 {de.max():.2f} over budget"

        # Arbitrary targets: metric excess of the pruned pick vs the oracle pick.
        # Only contracted for colors the palette can plausibly represent
        # (oracle distance < 30); for far-out-of-gamut targets the production
        # metric's dark-chromatic hue penalty is evaluated against
        # achromatic-reference hue angles (arctan2 of near-zero chroma), which
        # is noise — both pipelines return visually-pale washes there and the
        # pick difference is a pre-existing mapper property, not prune error.
        targets = rng.integers(0, 256, size=(200, 3)).tolist()
        _, full_rgbs_r = _map_and_refine(
            targets, full_code_df, full_rgb_df, colors, layer_count, layer_height,
        )
        _, pruned_rgbs_r = _map_and_refine(
            targets, pruned_code_df, pruned_rgb_df, colors, layer_count, layer_height,
        )
        target_lab = _lab(targets)
        oracle_dist = np.array([
            float(Color.perceptual_distance(target_lab[i], _lab([full_rgbs_r[i]]))[0])
            for i in range(len(targets))
        ])
        excess = np.array([
            float(Color.perceptual_distance(target_lab[i], _lab([pruned_rgbs_r[i]]))[0])
            for i in range(len(targets))
        ]) - oracle_dist
        plausible = oracle_dist < 30
        assert plausible.sum() >= 20, "target sample unexpectedly all out-of-gamut"
        assert excess[plausible].max() <= METRIC_EXCESS_BUDGET, (
            f"pruned pick is {excess[plausible].max():.2f} worse than oracle on "
            f"plausible targets"
        )
        assert excess.mean() <= 1.0, (
            f"mean excess {excess.mean():.2f} shows a systematic prune penalty"
        )
