"""Composition-pruned stack search for translucent filament sets.

Implements the hierarchical search from the tinting-voxel research note
``TD_ADAPTIVE_STACK_SEARCH.md`` (companion tinting-voxel-research
repository): in the translucent regime — every filament's neutral TD clears
the transparency threshold — a stack's color is dominated by its composition
(multiset of layers) and layer order is a secondary perturbation. The stage-1
reference set therefore shrinks from ``N**L`` ordered codes to exactly
``C(N+L-1, L)`` composition representatives (one canonical ordering each:
495 for 5 filaments x 8 layers vs 390,625 fully enumerated). Stage 2 then
refines the distinct orderings of every composition that ranks within a
margin of the best representative, under the production
``Color.perceptual_distance`` metric.

Pruning is never forced: it applies only when the automatic transparency
classification marks the whole set translucent; opaque and mixed sets keep
the exact full enumeration.

The ΔE00 budgets that gate this design against full enumeration as the
oracle are asserted in tests/unit/test_stack_prune.py at both 6 and 8 layers.
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

# Stage-2 candidate pool: compositions whose representative ranks within this
# ΔE00 margin of the best representative, by either the production metric or
# raw CIEDE2000. The margin covers the measured intra-composition order
# spread (mean ~3, max ~6.4 at 8 layers) plus slack, so a composition whose
# canonical ordering ranks poorly but whose other orderings win stays in the
# pool. The raw-CIEDE2000 channel guards against the production metric's
# dark-chromatic hue penalty hiding such compositions.
CANDIDATE_MARGIN_DELTA_E = 8.0

# Upper bound on compositions refined per input color.
MAX_CANDIDATE_COMPOSITIONS = 12


def is_translucent_set(
    colors: Colors,
    threshold_mm: Optional[float] = None,
    require_measured_td: bool = False,
) -> bool:
    """True when every filament's neutral TD meets the transparency threshold.

    Uses the same td_neutral data and default threshold (6.7 mm) as the
    frontend transparency classification. With ``require_measured_td=False``
    (the classification default, which drives the frontend layer-height hint)
    unmeasured colors fall back to their configured transmission distance.
    With ``require_measured_td=True`` (the prune gate) every color must carry
    a measured td_neutral: the prune's ΔE budget is validated only on
    TD1S-measured transparent sets, so approximation stays confined to that
    proven domain and everything else keeps exact full enumeration.
    """
    if threshold_mm is None:
        threshold_mm = settings.transparent_td_threshold
    items = colors.colors.values() if isinstance(colors.colors, dict) else []
    if not items:
        return False
    for color in items:
        td_neutral = getattr(color, "td_neutral", None)
        if require_measured_td and td_neutral is None:
            return False
        td = td_neutral if td_neutral is not None else color.td
        if td is None or td < threshold_mm:
            return False
    return True


def composition_codes(labels: list, layer_count: int) -> list:
    """One canonical (sorted) code per composition of layer_count over labels.

    Exactly ``C(len(labels) + layer_count - 1, layer_count)`` entries.
    """
    return [
        "".join(combo)
        for combo in itertools.combinations_with_replacement(sorted(labels), layer_count)
    ]


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


def _cap_distinct_compositions(
    pool: list,
    ref_codes: list,
    rep_pen: np.ndarray,
    rep_raw: np.ndarray,
    cap: int,
) -> list:
    """Keep the best ``cap`` DISTINCT composition codes from a margin pool.

    Matrix padding repeats the final composition (495 compositions pad to
    506 cells); duplicate entries are ranked identically, so deduplicate by
    code before applying the cap.
    """
    chosen: dict = {}
    for j in sorted(pool, key=lambda j: min(rep_pen[j], rep_raw[j])):
        code = ref_codes[j]
        if code in chosen:
            continue
        chosen[code] = j
        if len(chosen) >= cap:
            break
    return sorted(chosen.values())


def refine_matches(
    input_colors: list,
    stage1_codes: list,
    stage1_rgbs: list,
    code_matrix,
    rgb_matrix,
    colors: Colors,
    layer_height: float,
    code_to_rgb: Callable[[str], tuple],
    margin_delta_e: float = CANDIDATE_MARGIN_DELTA_E,
    max_compositions: int = MAX_CANDIDATE_COMPOSITIONS,
) -> tuple:
    """Order-refinement pass for composition-pruned nearest matches.

    Stage 1 (``Color.map_to_nearest_color`` against the pruned reference
    matrix, one canonical representative per composition) picks the nearest
    composition. Stage 2 re-ranks every composition whose representative
    falls within ``margin_delta_e`` of the best — by the production metric or
    raw CIEDE2000 — over all its distinct orderings, using the same
    perceptual metric as the production mapper. No-op for non-translucent
    sets, whose reference matrix already enumerates every ordering exactly.
    """
    if not is_translucent_set(colors, require_measured_td=True):
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
        rep_pen = Color.perceptual_distance(lab_color, ref_lab)
        rep_raw = Color.perceptual_distance_raw(lab_color, ref_lab)
        pool = sorted(
            set(np.where(rep_pen <= rep_pen.min() + margin_delta_e)[0])
            | set(np.where(rep_raw <= rep_raw.min() + margin_delta_e)[0])
        )
        if len(pool) > max_compositions:
            # Cap by DISTINCT compositions: the reference matrix is padded to
            # a rectangle (e.g. 495 compositions -> 506 cells), and the padded
            # copies of the final composition would otherwise consume cap
            # slots that belong to genuinely different compositions.
            pool = _cap_distinct_compositions(
                pool, ref_codes, rep_pen, rep_raw, max_compositions
            )

        best_code, best_rgb, best_dist = stage1_codes[i], stage1_rgbs[i], float(rep_pen.min())
        for idx in pool:
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
        "Prune refinement: %d inputs, %d orderings evaluated",
        len(input_colors), perms_evaluated,
    )
    return refined_codes, refined_rgbs
