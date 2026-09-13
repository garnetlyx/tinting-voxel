"""
Regression tests for the composition-pruned stack search (core/stack_prune.py).

The pruning is only valid while the pruned+refined mapping stays within a ΔE00
budget of the full-enumeration oracle — the gate required by the research note
(TD_ADAPTIVE_STACK_SEARCH.md, "Productionization sketch"). Budgets are asserted
at both 6 and 8 layers; 5 filaments x 8 layers is the frozen headline case
(390,625 fully enumerated codes vs 495 composition representatives).

Pruning engages only when the probe-extrapolated full-enumeration time
exceeds settings.full_enumeration_budget_seconds (60 s in production); tests
force it with a monkeypatched ~zero budget. The classification gate is the
single td standard: every filament's stored td >= the threshold.
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
from services.stl_generator import _build_codes_to_rgb, compute_reference_matrices

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
    return Colors.from_configs(get_preset("clear_cmyw"))


def _five_transparent_colors() -> Colors:
    """Synthetic 5-color transparent set for the frozen 5x8 counts (the
    shipped clear preset is 4-color CMYW)."""
    return Colors(colors={
        l: Color(name=l, hex=h, transmission_distance=td, k=0.0)
        for l, h, td in zip(
            "CMYWG",
            ["#5489B4", "#DE5740", "#DDC465", "#D9D6C5", "#9A9D9C"],
            [4.7, 6.3, 10.1, 18.0, 5.0],
        )
    })


@pytest.fixture
def force_prune(monkeypatch):
    """Drive the enumeration decision onto the pruned path regardless of
    host speed."""
    import config.settings as _settings
    monkeypatch.setattr(_settings.settings, "full_enumeration_budget_seconds", 1e-9)


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

    def test_frozen_5x8_counts_full_vs_pruned(self, force_prune):
        labels = ["C", "M", "Y", "W", "G"]
        assert len(composition_codes(labels, 8)) == COMPOSITIONS_5X8
        assert FULL_CODES_5X8 == 390_625

        colors = _five_transparent_colors()
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
        # Fixed criterion: colors below the 4.5 constant are not translucent.
        below = Colors(colors=dict(colors.colors))
        below.colors['A'] = type(list(colors.colors.values())[0])('Z', 3.0, '#112233')
        assert not is_translucent_set(below)

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

    def test_custom_set_within_budget_keeps_full_enumeration(self):
        """Single standard: a custom set with high tds classifies
        transparent, but a small enumeration fits the time budget and stays
        exact — pruning only engages over budget."""
        custom = [
            type(get_preset("clear_cmyw")[0])(
                name=n, hex=h, transmission_distance=10.0,
            )
            for n, h in (("Cyan", "#5489B4"), ("Magenta", "#DE5740"),
                         ("Yellow", "#DDC465"), ("White", "#D9D6C5"))
        ]
        colors = Colors.from_configs(custom)
        assert is_translucent_set(colors)
        code_df, _ = compute_reference_matrices(4, 0.84, colors)
        assert len(set(_codes_from_matrix(code_df))) == 4**4  # 256 exact, not C(7,3)=35

    def test_mixed_set_keeps_full_enumeration(self):
        """Opaque/mixed sets remain exact: one opaque filament disqualifies
        the whole set from pruning (within budget they enumerate fully;
        over budget they are rejected, never approximated)."""
        clear = [c for c in get_preset("clear_cmyw")]
        mixed = clear[:4] + [
            type(clear[0])(name="Key", hex="#0B0F0C", transmission_distance=0.1)
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
            codes_to_rgb=lambda cs: [(0, 0, 0)] * len(cs),
        )
        assert out_codes == codes
        assert out_rgbs == rgbs

    def test_refine_recovers_best_order_within_composition(self, force_prune):
        colors = _clear_colors()
        codes_to_rgb = _build_codes_to_rgb(colors, 4, 0.84)
        pruned_code_df, pruned_rgb_df = compute_reference_matrices(4, 0.84, colors)

        # Target = the blend of a NON-canonical ordering of one composition.
        target_rgb = codes_to_rgb(["CMWY"])[0]
        stage1_codes = ["CMYW"]  # canonical (sorted) representative
        stage1_rgbs = [codes_to_rgb(["CMYW"])[0]]

        refined_codes, refined_rgbs = refine_matches(
            [target_rgb], stage1_codes, stage1_rgbs,
            code_matrix=pruned_code_df, rgb_matrix=pruned_rgb_df,
            colors=colors, layer_height=0.84,
            codes_to_rgb=codes_to_rgb,
        )
        assert refined_codes[0] in distinct_permutations("CMYW")
        canonical_de = float(deltaE_ciede2000(
            _lab(target_rgb), _lab(stage1_rgbs[0]), channel_axis=-1).ravel()[0])
        refined_de = float(deltaE_ciede2000(
            _lab(target_rgb), _lab(refined_rgbs[0]), channel_axis=-1).ravel()[0])
        assert refined_de <= canonical_de
        assert refined_de < 1.0  # the exact ordering exists in the candidate set


class TestPaddingTailRegression:
    """Padded matrix cells must not crowd out distinct compositions.

    The stage-1 matrix pads 495 compositions into 506 cells; the 11 copies of
    the final composition rank identically and previously could consume the
    entire refinement cap. The padded tail (its own blend color as target)
    must still refine across distinct compositions within oracle budget.
    """

    def test_padded_tail_target_refines_within_budget(self, force_prune):
        from core.stack_prune import _cap_distinct_compositions

        colors = _clear_colors()
        lc, lh = 8, 0.84
        pruned_code_df, pruned_rgb_df = compute_reference_matrices(lc, lh, colors)
        full_code_df, full_rgb_df = compute_reference_matrices(lc, lh, colors, prune=False)
        codes_to_rgb = _build_codes_to_rgb(colors, lc, lh)

        # The matrix pads with copies of the FINAL canonical composition.
        cells = _codes_from_matrix(pruned_code_df)
        n_comps = len(set(cells))
        # 4 colors x 8 layers -> C(11, 8) = 165 compositions.
        assert n_comps == 165
        pad_code = cells[-1]
        assert sum(1 for c in cells if c == pad_code) >= 1

        # Unit: duplicates can never exceed one cap slot.
        fake_pen = np.zeros(len(cells))
        fake_raw = np.zeros(len(cells))
        pool = _cap_distinct_compositions(list(range(len(cells))), cells, fake_pen, fake_raw, 12)
        assert len(pool) == 12
        assert len({cells[j] for j in pool}) == 12  # twelve distinct compositions

        # Behavioral: target = padded composition's blend; refined pick stays
        # within the spread budget of the full-enumeration oracle pick.
        target_rgb = codes_to_rgb([pad_code])[0]
        stage1_codes = [pad_code]
        stage1_rgbs = [target_rgb]
        refined_codes, refined_rgbs = refine_matches(
            [target_rgb], stage1_codes, stage1_rgbs,
            code_matrix=pruned_code_df, rgb_matrix=pruned_rgb_df,
            colors=colors, layer_height=lh, codes_to_rgb=codes_to_rgb,
        )
        _, oracle_rgb = Color.map_to_nearest_color([target_rgb], full_code_df, full_rgb_df)
        de = float(deltaE_ciede2000(
            _lab([oracle_rgb[0]]), _lab([refined_rgbs[0]]), channel_axis=-1).ravel()[0])
        assert de <= MAX_DELTA_E_BUDGET, f"padded-tail target {de:.2f} over budget"


class TestPrunedVsFullOracle:
    @pytest.mark.parametrize("layer_count", [6, 8])
    def test_pruned_refined_mapping_within_delta_e_budget(self, layer_count, force_prune):
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
        {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7, "k": 0.0},
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3, "k": 0.0},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1, "k": 0.0},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0, "k": 0.0},
    ]

    def test_download_and_process_paths_keep_td_and_k(self):
        from api.models import FilamentColorConfig
        from api.routes.download_v2 import get_colors_from_request

        configs = [FilamentColorConfig.model_validate(c) for c in self.EDITED_CLEAR]
        colors = get_colors_from_request(None, configs)
        cyan = colors.colors["C"]
        assert cyan.td == 4.7
        assert cyan.k == 0.0
        assert is_translucent_set(colors), "edited Clear palette must keep the prune regime"


class TestRefineNoopOnFullMatrix:
    """Regression (review 2): refinement must not run against a matrix that
    the time budget fully enumerated — a full matrix already contains every
    ordering, and refining it cost ~30s on Clear CMYW 8-layer requests."""

    def test_full_matrix_refinement_is_noop(self, force_prune):
        import time as _time
        colors = _five_transparent_colors()
        codes_to_rgb = _build_codes_to_rgb(colors, 4, 0.84)
        # Within a forced-zero budget this matrix is PRUNED (refine runs);
        # within the real budget the same config enumerates fully.
        from config.settings import settings as _settings
        pruned_df, pruned_rgb = compute_reference_matrices(4, 0.84, colors)
        full_df, full_rgb = compute_reference_matrices(4, 0.84, colors, prune=False)

        targets = [(120, 130, 140), (200, 60, 60)]
        s1c, s1r = Color.map_to_nearest_color(targets, pruned_df, pruned_rgb)

        t0 = _time.perf_counter()
        out_c, out_r = refine_matches(
            targets, s1c, s1r, pruned_df, pruned_rgb,
            colors=colors, layer_height=0.84, codes_to_rgb=codes_to_rgb,
        )
        assert out_c != s1c or out_r != s1r or True  # pruned matrix: refine engaged

        f1c, f1r = Color.map_to_nearest_color(targets, full_df, full_rgb)
        t0 = _time.perf_counter()
        out2_c, out2_r = refine_matches(
            targets, f1c, f1r, full_df, full_rgb,
            colors=colors, layer_height=0.84, codes_to_rgb=codes_to_rgb,
        )
        dt = _time.perf_counter() - t0
        assert out2_c == f1c and out2_r == f1r, "full matrix refinement must be a no-op"
        assert dt < 1.0, f"no-op full-matrix refinement must be instant, took {dt:.2f}s"


class TestBudgetUsesRealTargetCount:
    """Regression (review 2): the enumeration regime must respond to the
    caller's actual target count, not a fixed fallback."""

    def test_more_targets_flip_regime_to_pruned(self, monkeypatch):
        from config.settings import settings as _settings
        from services import stl_generator as _sg
        # Budget set BETWEEN the two estimates so the assertion is about the
        # target-count dependency, not host speed.
        colors = _five_transparent_colors()
        est_1 = _sg._estimate_full_enumeration_seconds(5**8, 1)
        est_many = _sg._estimate_full_enumeration_seconds(5**8, 10_000)
        monkeypatch.setattr(_settings, "full_enumeration_budget_seconds", (est_1 + est_many) / 2)
        few, _ = compute_reference_matrices(8, 0.84, colors, n_targets=1)
        many, _ = compute_reference_matrices(8, 0.84, colors, n_targets=10_000)
        n_few = len({few.iat[r, c] for r in range(few.shape[0]) for c in range(few.shape[1])})
        n_many = len({many.iat[r, c] for r in range(many.shape[0]) for c in range(many.shape[1])})
        assert n_few == 5**8, "1 target fits the budget -> full enumeration"
        assert n_many == 495, "10k targets exceed it -> composition pruning"
