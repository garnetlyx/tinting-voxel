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

from core.color_materials import Color, Colors

logger = logging.getLogger(__name__)

# Transparency classification threshold (mm) on the stored td scale — the
# same number blending uses, one standard for every set. 4.5 sits in the gap
# between the calibrated families (bambu folded 0.27-0.61 vs clear staircase
# means 4.7-18.0), so clear CMYW classifies transparent and bambu sets
# opaque. Deliberately a literal constant, not a setting: it is a property of
# the calibrated data, not an environment knob, and the frontend hint uses
# the same value (TRANSPARENT_TD_THRESHOLD_MM in src/api/types.ts).
TRANSPARENT_TD_THRESHOLD_MM = 4.5

# Distinct orderings considered per composition during refinement.
# Covers the worst realistic case (5 filaments x 8 layers -> 5040 orderings);
# exotic wider sets are capped deterministically (evenly sampled).
MAX_PERMS_PER_COMPOSITION = 8192

# Stage-2 candidate pool: compositions whose representative ranks within this
# ΔE00 margin of the best representative, by either the production metric or
# raw CIEDE2000. The raw-CIEDE2000 channel guards against the production
# metric's dark-chromatic hue penalty hiding such compositions.
#
# Retuned for the corrected per-channel blend (the reference-matrix cache key
# previously dropped td_rgb, so production blended with scalar-td fallback
# and these budgets were calibrated against that behavior). Under the real
# staircase TDs the intra-composition order spread is wider: a 5c x 8L sweep
# against the full-enumeration oracle gives, at margin=48/cap=128,
# reachable ΔE00 mean 0.27 / max 1.15 and plausible-target metric excess
# max 2.20 / mean 0.10 (budgets 1.5 / 7.5 / 4.0 / 1.0). The previous
# margin=16/cap=32 values measured excess 8.52 at 8 layers under the same
# corrected blend.
CANDIDATE_MARGIN_DELTA_E = 48.0

# Upper bound on compositions refined per input color.
MAX_CANDIDATE_COMPOSITIONS = 128


def is_translucent_set(colors: Colors) -> bool:
    """True when every td value blending uses meets the transparency threshold.

    Single standard: the td numbers blending actually reads — per-channel
    td_rgb when the filament carries staircase measurements, else the scalar
    td broadcast — every channel >= the one fixed 4.5 mm constant. A set whose
    every channel transmits weakly (all td_ch >= 4.5) has order-insensitive
    stacking, which is what the composition-pruning ΔE oracle validates.
    Paper-data presets: bambu (paper-fitted folds) sits at 1.94-2.22 and the
    clear presets carry per-channel staircases down to ~1.0 mm in their most
    absorbing channel — the accurate per-channel model makes real clear
    stacks order-sensitive, so neither ships as prunable; only sets that are
    uniformly high-td on every channel (e.g. customs at 10-30 mm) classify
    transparent.
    """
    items = colors.colors.values() if isinstance(colors.colors, dict) else []
    if not items:
        return False
    for color in items:
        td_rgb = color.td_rgb
        tds = tuple(td_rgb) if td_rgb is not None else (color.td,)
        if any(td is None or td < TRANSPARENT_TD_THRESHOLD_MM for td in tds):
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


def _matrix_is_fully_enumerated(code_matrix) -> bool:
    """True when the matrix holds every ordered code (not pruned).

    A pruned matrix contains only canonical (character-sorted)
    representatives; any non-sorted cell proves full enumeration. Full
    matrices are overwhelmingly unsorted, so the scan exits immediately.
    """
    for r in range(code_matrix.shape[0]):
        for c in range(code_matrix.shape[1]):
            code = code_matrix.iat[r, c]
            if list(code) != sorted(code):
                return True
    return False


def refine_matches(
    input_colors: list,
    stage1_codes: list,
    stage1_rgbs: list,
    code_matrix,
    rgb_matrix,
    colors: Colors,
    layer_height: float,
    codes_to_rgb: Callable[[list[str]], list[tuple]],
    margin_delta_e: float = CANDIDATE_MARGIN_DELTA_E,
    max_compositions: int = MAX_CANDIDATE_COMPOSITIONS,
) -> tuple:
    """Order-refinement pass for composition-pruned nearest matches.

    Stage 1 (``Color.map_to_nearest_color`` against the pruned reference
    matrix, one canonical representative per composition) picks the nearest
    composition. Stage 2 re-ranks every composition whose representative
    falls within ``margin_delta_e`` of the best — by the production metric or
    raw CIEDE2000 — over all its distinct orderings, using the same
    perceptual metric as the production mapper.

    No-op for non-translucent sets AND for matrices that were fully
    enumerated (a full matrix already contains every ordering exactly, so
    refinement cannot improve it — and running it anyway costs tens of
    seconds on large translucent grids).
    """
    if not is_translucent_set(colors):
        return stage1_codes, stage1_rgbs
    if _matrix_is_fully_enumerated(code_matrix):
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
                # Batch-blend every ordering of the composition once; the
                # result is reused by every subsequent input color.
                codes = distinct_permutations(rep_code)
                perm_cache[rep_code] = (
                    codes,
                    np.array(codes_to_rgb(codes), dtype=np.float64),
                )
            perms, perm_rgb = perm_cache[rep_code]
            if len(perm_rgb) > 1:
                perm_lab = _lab(perm_rgb / 255.0)
                perm_dists = Color.perceptual_distance(lab_color, perm_lab)
                perms_evaluated += len(perms)
                local = int(np.argmin(perm_dists))
                if float(perm_dists[local]) < best_dist:
                    best_dist = float(perm_dists[local])
                    best_code = perms[local]
                    # Keep the same float domain as the stage-1 rgb it may
                    # replace; callers round to the image domain themselves.
                    best_rgb = tuple(float(v) for v in perm_rgb[local])
                # The stage-1 representative itself stays a candidate via the
                # first entry of its (sorted) permutation list.

        refined_codes[i] = best_code
        refined_rgbs[i] = best_rgb

    logger.info(
        "Prune refinement: %d inputs, %d orderings evaluated",
        len(input_colors), perms_evaluated,
    )
    return refined_codes, refined_rgbs
