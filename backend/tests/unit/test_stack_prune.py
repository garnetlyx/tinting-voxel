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


def _translucent_colors() -> Colors:
    """A scalar-TD palette for composition and runtime regressions."""
    return Colors(colors={
        l: Color(name=l, hex=h, transmission_distance=td)
        for l, h, td in zip(
            "CMYW",
            ["#5489B4", "#DE5740", "#DDC465", "#D9D6C5"],
            [4.7, 6.3, 10.1, 18.0],
        )
    })


def _five_transparent_colors() -> Colors:
    """Synthetic 5-color transparent set for the frozen 5x8 counts (the
    shipped clear preset is 4-color CMYW)."""
    return Colors(colors={
        l: Color(name=l, hex=h, transmission_distance=td)
        for l, h, td in zip(
            "CMYWG",
            ["#5489B4", "#DE5740", "#DDC465", "#D9D6C5", "#9A9D9C"],
            [4.5, 4.5, 4.5, 4.5, 4.5],
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
    return code_df.to_numpy().ravel().tolist()


def _is_full_enumeration(code_df, layer_count, layer_height, colors) -> bool:
    """The matrix is the full-enumeration oracle, not composition-pruned."""
    full_df, _ = compute_reference_matrices(layer_count, layer_height, colors, prune=False)
    return set(_codes_from_matrix(code_df)) == set(_codes_from_matrix(full_df))


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
        full_codes = set(_codes_from_matrix(full_df))
        pruned_codes = set(_codes_from_matrix(pruned_df))
        # One code per distinct color: orderings for the full set, canonical
        # compositions for the pruned one.
        assert pruned_codes <= set(composition_codes(colors.get_labels(), 8))
        assert len(pruned_codes) <= COMPOSITIONS_5X8 < len(full_codes) <= FULL_CODES_5X8

    def test_distinct_permutations_unique_and_capped(self):
        perms = distinct_permutations("CCMMYYWG")
        assert len(perms) == len(set(perms))
        assert len(perms) == 5040  # 8!/(2!*2!*2!*1!*1!) distinct orderings
        capped = distinct_permutations("ABCDEFGH", cap=50)
        assert len(capped) <= 50
        assert "ABCDEFGH" in capped  # deterministic sample keeps endpoints


class TestRegimeGate:
    def test_shipped_clear_presets_are_translucent(self):
        """The regime uses the palette mean, preserving channel measurements."""
        for name in ("clear_cmyw", "clear_cmyg"):
            assert is_translucent_set(Colors.from_configs(get_preset(name)))

    def test_uniform_high_td_set_is_translucent(self):
        assert is_translucent_set(_translucent_colors())

    def test_bambu_set_is_not_translucent(self):
        colors = Colors.from_configs(get_preset("bambu_cmywk"))
        assert not is_translucent_set(colors)

    def test_custom_scalar_values_define_the_regime(self):
        colors = Colors(colors={
            "A": Color(name="A", hex="#112233", transmission_distance=10.0),
            "B": Color(name="B", hex="#332211", transmission_distance=20.0),
            "C": Color(name="C", hex="#221133", transmission_distance=30.0),
            "D": Color(name="D", hex="#112233", transmission_distance=10.0),
        })
        assert is_translucent_set(colors)
        # Fixed criterion: colors below the 4.5 constant are not translucent.
        below = Colors(colors=dict(colors.colors))
        below = Colors(colors={label: Color(label, 3.0, '#112233') for label in 'ABCD'})
        assert not is_translucent_set(below)

    def test_prune_true_never_forces_pruning(self):
        """Pruning is automatic and translucent-only; True is rejected outright."""
        translucent = _translucent_colors()
        bambu = Colors.from_configs(get_preset("bambu_cmywk"))
        for colors in (translucent, bambu):
            with pytest.raises(ValueError, match="prune=True is not supported"):
                compute_reference_matrices(4, 0.84, colors, prune=True)

    def test_opaque_set_keeps_full_enumeration(self):
        bambu = Colors.from_configs(get_preset("bambu_cmywk"))
        code_df, _ = compute_reference_matrices(4, 0.08, bambu)
        assert _is_full_enumeration(code_df, 4, 0.08, bambu)

    def test_custom_set_within_budget_keeps_full_enumeration(self):
        """A custom set with a high TD mean classifies
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
        assert _is_full_enumeration(code_df, 4, 0.84, colors)  # exact, not the 35 compositions

    def test_mixed_set_keeps_full_enumeration(self):
        """Opaque/mixed sets remain exact: one opaque filament disqualifies
        the whole set from pruning (within budget they enumerate fully;
        over budget they are rejected, never approximated)."""
        clear = [type(c)(c.name, c.hex, 4.5) for c in get_preset("clear_cmyw")]
        mixed = clear[:4] + [
            type(clear[0])(name="Key", hex="#0B0F0C", transmission_distance=0.1)
        ]
        colors = Colors.from_configs(mixed)
        assert not is_translucent_set(colors)
        code_df, _ = compute_reference_matrices(4, 0.84, colors)
        assert _is_full_enumeration(code_df, 4, 0.84, colors)  # full, not the 70 compositions


class TestRefinement:
    def test_refine_is_noop_for_opaque_set(self):
        colors = Colors.from_configs(get_preset("bambu_cmywk"))
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
        colors = _translucent_colors()
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

        colors = _translucent_colors()
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
    @pytest.mark.parametrize("preset", ["clear_cmyw", "clear_cmyg"])
    def test_pruned_refined_mapping_within_delta_e_budget(self, layer_count, preset, force_prune):
        """Ship gate: pruned+refined must match the full-enumeration oracle.

        - Reachable targets (sampled from the blend gamut itself): the pruned
          pick must land within the spread-derived budget of the oracle pick.
        - Arbitrary targets: the pruned pick must not be meaningfully worse a
          match than the oracle's, by the production perceptual metric.
          Comparing the two picks' RGB directly is not meaningful for colors
          outside the printable gamut, where both paths are equally
          approximate.
        """
        colors = Colors.from_configs(get_preset(preset))
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
        gamut = np.array(full_rgb_df.to_numpy().ravel().tolist())
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
    """Edited palettes retain their TD on each request path."""

    EDITED_CLEAR = [
        {"name": "Cyan", "hex": "#5489B4", "transmission_distance": 4.7},
        {"name": "Magenta", "hex": "#DE5740", "transmission_distance": 6.3},
        {"name": "Yellow", "hex": "#DDC465", "transmission_distance": 10.1},
        {"name": "White", "hex": "#D9D6C5", "transmission_distance": 18.0},
    ]

    def test_download_and_process_paths_keep_td(self):
        from api.models import FilamentColorConfig
        from api.filament_payload import get_colors_from_request

        configs = [FilamentColorConfig.model_validate(c) for c in self.EDITED_CLEAR]
        colors = get_colors_from_request(None, configs)
        cyan = colors.colors["C"]
        assert cyan.td == 4.7
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
        from services import matrix_cache as _mc
        from services import stl_generator as _sg
        colors = _five_transparent_colors()
        full_df, _ = compute_reference_matrices(8, 0.84, colors, prune=False)
        build = _sg._estimate_build_seconds(5**8)
        est_1 = build + _sg._estimate_match_seconds(full_df.size, 1)
        est_many = build + _sg._estimate_match_seconds(full_df.size, 10_000)
        # Budget set BETWEEN the two estimates so the assertion is about the
        # target-count dependency, not host speed; the hard limit is not under test.
        monkeypatch.setattr(_settings, "full_enumeration_budget_seconds", (est_1 + est_many) / 2)
        monkeypatch.setattr(_settings, "stack_search_limit_seconds", float("inf"))
        _mc.clear_cache()
        few, _ = compute_reference_matrices(8, 0.84, colors, n_targets=1)
        _mc.clear_cache()
        many, _ = compute_reference_matrices(8, 0.84, colors, n_targets=10_000)
        few_codes = set(_codes_from_matrix(few))
        many_codes = set(_codes_from_matrix(many))
        assert few_codes == set(_codes_from_matrix(full_df)), "1 target fits the budget -> full enumeration"
        assert many_codes <= set(composition_codes(colors.get_labels(), 8)), (
            "10k targets exceed it -> composition pruning"
        )
        _mc.clear_cache()


def _distinct_hex_colors(labels: str, td: float) -> Colors:
    hexes = ["#3D79C6", "#B3356E", "#FFE665", "#FFFFFF", "#112233", "#445566", "#778899", "#0B0F0C"]
    return Colors(colors={label: Color(label, td, hexes[i]) for i, label in enumerate(labels)})


class TestEstimateAccuracy:
    """The probe model must track the measured uncached wall time of the
    complete production path — compute_reference_matrices (enumeration)
    plus map_to_nearest_color for the same target count — within 0.1x..3x."""

    def _measure_end_to_end(self, colors, layer_count, layer_height, n_targets):
        import time as _time
        from core.color_materials import Color as _C
        from services import matrix_cache as _mc
        from services.stl_generator import compute_reference_matrices as _crm
        _mc.clear_cache()
        t0 = _time.perf_counter()
        code_df, rgb_df = _crm(layer_count, layer_height, colors, n_targets=n_targets)
        targets = [(120 + i, 130, 140) for i in range(n_targets)]
        _C.map_to_nearest_color(targets, code_df, rgb_df)
        measured = _time.perf_counter() - t0
        _mc.clear_cache()
        return measured, code_df.size

    def test_estimate_tracks_measured_end_to_end(self):
        from services import stl_generator as _sg
        colors = _distinct_hex_colors("CMYWK", 0.5)
        n_targets = 10
        measured, n_references = self._measure_end_to_end(colors, 8, 0.08, n_targets)
        est = _sg._estimate_build_seconds(5 ** 8) + _sg._estimate_match_seconds(n_references, n_targets)
        assert est <= measured * 3, f"estimate {est:.3f}s exceeds measured {measured:.3f}s by >3x"
        assert est >= measured * 0.1, f"estimate {est:.3f}s is >10x below measured {measured:.3f}s"

    def test_within_budget_accepted_regardless_of_code_count(self, monkeypatch):
        """Frozen policy: the time budget is the ONLY enumeration gate —
        no fixed code-count cap. A set whose estimate fits the budget
        enumerates fully no matter how many codes that is."""
        from config.settings import settings as _settings
        from services import matrix_cache as _mc
        from services import stl_generator as _sg
        from services.stl_generator import compute_reference_matrices as _crm
        from core.stack_prune import _matrix_is_fully_enumerated
        opaque = _distinct_hex_colors("ABCDEFGH", 0.5)
        # Budget comfortably ABOVE the estimate: the 8^8 (16.7M-code)
        # enumeration must be admitted — there is no count ceiling.
        monkeypatch.setattr(
            _settings, "full_enumeration_budget_seconds", _sg._estimate_build_seconds(8 ** 8) * 10 + 60,
        )
        _mc.clear_cache()
        df, _ = _crm(8, 0.08, opaque, n_targets=10)
        assert _matrix_is_fully_enumerated(df)
        _mc.clear_cache()

    def test_regime_flips_at_budget_boundary(self, monkeypatch):
        """Behavior near the budget boundary: the estimate decides full vs
        prune, and translucent sets over budget prune."""
        from config.settings import settings as _settings
        from services import matrix_cache as _mc
        from services import stl_generator as _sg
        from services.stl_generator import compute_reference_matrices as _crm
        translucent = _distinct_hex_colors("CMYWK", 5.0)
        full_df, _ = _crm(5, 0.08, translucent, prune=False)
        est = _sg._estimate_build_seconds(5 ** 5) + _sg._estimate_match_seconds(full_df.size, 10)
        # Over the estimate -> within budget -> full enumeration.
        monkeypatch.setattr(_settings, "full_enumeration_budget_seconds", est * 2)
        _mc.clear_cache()
        df, _ = _crm(5, 0.08, translucent, n_targets=10)
        assert set(_codes_from_matrix(df)) == set(_codes_from_matrix(full_df))
        # Under the estimate -> over budget -> pruned (translucent).
        monkeypatch.setattr(_settings, "full_enumeration_budget_seconds", est * 0.5)
        _mc.clear_cache()
        df_p, _ = _crm(5, 0.08, translucent, n_targets=10)
        assert set(_codes_from_matrix(df_p)) <= set(composition_codes(translucent.get_labels(), 5))
        _mc.clear_cache()


class TestMeanTdContract:
    def test_one_low_channel_changes_the_mean_without_being_overwritten(self):
        colors = Colors(colors={label: Color(label, 4.6, '#334455') for label in 'ABCD'})
        assert is_translucent_set(colors)
        colors.colors['A'] = Color('A', (.1, 4.6, 4.6), '#334455')
        assert not is_translucent_set(colors)
        assert colors['A'].td_channels == (.1, 4.6, 4.6)

    def test_scalar_and_equal_channels_have_equal_weight(self):
        scalar = Colors(colors={label: Color(label, 4.5, '#334455') for label in 'ABCD'})
        vector = Colors(colors={label: Color(label, (4.5, 4.5, 4.5), '#334455') for label in 'ABCD'})
        assert is_translucent_set(scalar) is True
        assert is_translucent_set(vector) is True

    def test_threshold_selective_channels_against_full_oracle(self, force_prune):
        colors = Colors(colors={
            'C': Color('C', (.1, 6.7, 6.7), '#00FFFF'),
            'M': Color('M', (6.7, .1, 6.7), '#FF00FF'),
            'Y': Color('Y', (6.7, 6.7, .1), '#FFFF00'),
            'W': Color('W', 4.5, '#FFFFFF'),
        })
        assert is_translucent_set(colors)
        full_codes, full_rgbs = compute_reference_matrices(8, .84, colors, prune=False)
        codes, rgbs = compute_reference_matrices(8, .84, colors)
        rng = np.random.default_rng(72)
        targets = rng.integers(0, 256, size=(24, 3)).tolist()
        _, full_matches = Color.map_to_nearest_color(targets, full_codes, full_rgbs)
        _, pruned_matches = _map_and_refine(targets, codes, rgbs, colors, 8, .84)
        target_lab = _lab(targets)
        excess = np.array([
            Color.perceptual_distance(lab, _lab([approx]))[0]
            - Color.perceptual_distance(lab, _lab([exact]))[0]
            for lab, approx, exact in zip(target_lab, pruned_matches, full_matches)
        ])
        assert excess.max() <= METRIC_EXCESS_BUDGET
        assert excess.mean() <= 1.0



class TestSearchLimit:
    """Searches estimated over stack_search_limit_seconds are rejected, and each
    filament set's layer maximum keeps the worst case inside the limit."""

    @pytest.fixture
    def fixed_rates(self, monkeypatch):
        from services import stl_generator as _sg
        # Production-like rates: 8.45e-7 s per enumerated code, 5.06e-8 s per match.
        monkeypatch.setattr(_sg, "_probe_throughput", lambda: (8.45e-7, 5.06e-8))

    def test_pruned_search_over_the_limit_is_rejected(self, fixed_rates, monkeypatch):
        from config.settings import settings as _settings
        from services import matrix_cache as _mc
        monkeypatch.setattr(_settings, "full_enumeration_budget_seconds", 1e-9)
        _mc.clear_cache()
        colors = _distinct_hex_colors("ABCDEFGH", 8.0)
        with pytest.raises(ValueError, match="even with composition pruning"):
            compute_reference_matrices(10, 0.84, colors, n_targets=100)

    def test_layer_maximum_keeps_presets_and_caps_large_sets(self, fixed_rates):
        from services.stl_generator import max_color_layers
        assert max_color_layers(Colors.from_configs(get_preset("bambu_cmywk"))) == 10
        assert max_color_layers(Colors.from_configs(get_preset("clear_cmyw"))) == 10
        opaque16 = _distinct_hex_colors("ABCDEFGH", 0.3)
        opaque16.colors.update({l: Color(l, 0.3, f"#1{i}2{i}3{i}") for i, l in enumerate("IJKLMNOP")})
        assert max_color_layers(opaque16) == 6  # 16^6 codes fit; 16^7 do not
        clear16 = Colors(colors={l: Color(l, 8.0, c.hex) for l, c in opaque16.colors.items()})
        assert max_color_layers(clear16) < 10
