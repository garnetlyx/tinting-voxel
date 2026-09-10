"""Composition-pruned stack search for translucent filament sets.

Implements the hierarchical search from the tinting-voxel research note
``docs/TD_ADAPTIVE_STACK_SEARCH.md``: in the translucent regime — every
filament's neutral TD clears the transparency threshold — a stack's color is
dominated by its composition (multiset of layers) and layer order is a
secondary perturbation. The reference set therefore shrinks from ``N**L``
ordered codes to ``C(N+L-1, L)`` composition representatives. Each input is
then matched against the top-K compositions (by the production
``Color.perceptual_distance`` metric) refined over all distinct orderings of
those compositions.

Correctness is bounded by the intra-composition order spread (measured on the
staircase-calibrated clear set at 8 layers: mean ~3, max ~6.4 ΔE00) and
guarded by a regression test against full enumeration as the oracle
(tests/unit/test_stack_prune.py). Opaque and mixed sets keep the exact full
enumeration.
"""
import itertools
import logging
from typing import Callable, Optional

import numpy as np

from config.settings import settings
from core.color_materials import Color, Colors

logger = logging.getLogger(__name__)

# Distinct orderings considered per composition during refinement.
# Covers the worst realistic case (5 filaments x 8 layers -> 5040 orderings);
# exotic wider sets are capped deterministically (evenly sampled).
MAX_PERMS_PER_COMPOSITION = 8192

# Compositions refined per input color. The stage-1 winner plus a few
# neighbours: bounds the cost at top_k * MAX_PERMS_PER_COMPOSITION blends per
# input while recovering compositions whose best ordering outranks the
# canonical representative of the stage-1 winner.
DEFAULT_TOP_K_COMPOSITIONS = 5


def is_translucent_set(colors: Colors, threshold_mm: Optional[float] = None) -> bool:
    """True when every filament's neutral TD meets the transparency threshold.

    Uses the same td_neutral data and default threshold (6.7 mm) as the
    frontend transparency classification; unmeasured colors fall back to
    their configured transmission distance.
    """
    if threshold_mm is None:
        threshold_mm = settings.transparent_td_threshold
    items = colors.colors.values() if isinstance(colors.colors, dict) else []
    if not items:
        return False
    for color in items:
        td_neutral = getattr(color, "td_neutral", None)
        td = td_neutral if td_neutral is not None else color.td
        if td is None or td < threshold_mm:
            return False
    return True


def composition_codes(labels: list, layer_count: int) -> list:
    """Canonical (sorted) code per composition of layer_count over labels."""
    return [
        "".join(combo)
        for combo in itertools.combinations_with_replacement(sorted(labels), layer_count)
    ]


def _interleaved_ordering(combo: tuple) -> str:
    """Round-robin ordering starting from the most frequent label.

    Gives each composition a hue-diverse representative whose member ordering
    differs from both the sorted and reversed forms.
    """
    from collections import Counter

    counts = Counter(combo)
    queue = [label for label, _ in counts.most_common()]
    out = []
    qi = 0
    for _ in combo:
        # advance to a label that still has budget (round robin over labels)
        while counts[queue[qi % len(queue)]] == 0:
            qi += 1
        label = queue[qi % len(queue)]
        counts[label] -= 1
        out.append(label)
        qi += 1
    return "".join(out)


def composition_rep_codes(labels: list, layer_count: int) -> list:
    """Three diverse orderings per composition (sorted, reversed, interleaved).

    A single canonical ordering can misrepresent a composition by more than
    the measured intra-composition spread, because the production metric's
    dark-chromatic hue penalty amplifies ordering-driven hue differences.
    Diverse representatives keep the stage-1 ranking honest while the matrix
    stays at 3x C(N+L-1, L) candidates instead of N^L.
    """
    codes = []
    for combo in itertools.combinations_with_replacement(sorted(labels), layer_count):
        canonical = "".join(combo)
        reversed_code = canonical[::-1]
        interleaved = _interleaved_ordering(combo)
        codes.append(canonical)
        if reversed_code != canonical:
            codes.append(reversed_code)
        if interleaved not in (canonical, reversed_code):
            codes.append(interleaved)
    return codes


def distinct_permutations(code: str, cap: int = MAX_PERMS_PER_COMPOSITION) -> list:
    """All unique orderings of a code's letters, deterministically capped."""
    perms = sorted(set("".join(p) for p in itertools.permutations(sorted(code))))
    if len(perms) > cap:
        # Evenly sample the sorted ordering space so the cap stays representative
        # rather than biased toward the lexicographic head.
        idx = np.linspace(0, len(perms) - 1, cap).round().astype(int)
        perms = [perms[i] for i in sorted(set(idx.tolist()))]
    return perms


def _lab(rgb01: np.ndarray) -> np.ndarray:
    """Convert an (N, 3) RGB array in [0, 1] to CIELAB (N, 3)."""
    from skimage.color import rgb2lab

    return rgb2lab(np.asarray(rgb01, dtype=np.float64).reshape(-1, 1, 3)).reshape(-1, 3)


def refine_matches(
    input_colors: list,
    stage1_codes: list,
    stage1_rgbs: list,
    code_matrix,
    rgb_matrix,
    colors: Colors,
    layer_height: float,
    code_to_rgb: Callable[[str], tuple],
    top_k: int = DEFAULT_TOP_K_COMPOSITIONS,
) -> tuple:
    """Two-stage refinement for composition-pruned nearest matches.

    Stage 1 (``Color.map_to_nearest_color`` against the pruned reference
    matrix) picks the nearest composition representative. Stage 2 re-ranks the
    top ``top_k`` compositions per input over all their distinct orderings,
    using the same perceptual metric as the production mapper. No-op for
    non-translucent sets, whose reference matrix already enumerates every
    ordering exactly.
    """
    if not is_translucent_set(colors):
        return stage1_codes, stage1_rgbs

    ref_codes = []
    ref_rgb01 = []
    for r in range(code_matrix.shape[0]):
        for c in range(code_matrix.shape[1]):
            ref_codes.append(code_matrix.iat[r, c])
            ref_rgb01.append(np.asarray(rgb_matrix.iat[r, c], dtype=np.float64) / 255.0)
    ref_rgb01 = np.array(ref_rgb01)
    ref_lab = _lab(ref_rgb01)

    inp_lab = _lab(np.array(input_colors, dtype=np.float64) / 255.0)

    perm_cache: dict = {}
    refined_codes: list = [None] * len(input_colors)
    refined_rgbs: list = [None] * len(input_colors)
    perms_evaluated = 0

    for i, lab_color in enumerate(inp_lab):
        # Candidate selection runs on two rankings: the production metric and
        # raw CIEDE2000. The dark-chromatic hue penalty in the production
        # metric can hide a composition whose canonical ordering has a misaligned
        # hue but whose other orderings win; the raw ranking keeps those in play.
        # The final pick is always ranked by the production metric.
        rep_pen = Color.perceptual_distance(lab_color, ref_lab)
        rep_raw = Color.perceptual_distance_raw(lab_color, ref_lab)
        top = sorted(set(np.argsort(rep_pen)[:top_k]) | set(np.argsort(rep_raw)[:top_k]))

        best_code, best_rgb, best_dist = stage1_codes[i], stage1_rgbs[i], float(rep_pen.min())
        for idx in top:
            rep_code = ref_codes[idx]
            if rep_code not in perm_cache:
                perm_cache[rep_code] = distinct_permutations(rep_code)
            perms = perm_cache[rep_code]
            if len(perms) > 1:
                perm_rgb = np.array([code_to_rgb(p) for p in perms], dtype=np.float64)
                perm_lab = _lab(perm_rgb / 255.0)
                perm_dists = Color.perceptual_distance(lab_color, perm_lab)
                perms_evaluated += len(perms)
                local = int(np.argmin(perm_dists))
                if float(perm_dists[local]) < best_dist:
                    best_dist = float(perm_dists[local])
                    best_code = perms[local]
                    best_rgb = tuple(int(round(v)) for v in perm_rgb[local])
                # The stage-1 representative itself stays a candidate via the
                # first entry of its (sorted) permutation list.

        refined_codes[i] = best_code
        refined_rgbs[i] = best_rgb

    logger.info(
        "Prune refinement: %d inputs, top-%d compositions each, %d orderings evaluated",
        len(input_colors), top_k, perms_evaluated,
    )
    return refined_codes, refined_rgbs
