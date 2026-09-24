"""Composition search with full order refinement within a ranked candidate pool.

The material-set TD mean determines the transparency regime. Over-budget
searches use one representative per composition, then refine the best
compositions by the same color-distance metric as exhaustive search.
The accepted error against exhaustive search is tested at six and eight layers.
"""
import itertools
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import numpy as np

from core.color_materials import Color, Colors
from core.parallel import worker_threads

logger = logging.getLogger(__name__)

# Palette-wide arithmetic TD mean, in millimetres. The threshold separates
# the characterized production palettes and is checked against the full
# enumeration oracle on both scalar and channel-specific measurements.
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
CANDIDATE_MARGIN_DELTA_E = 48.0

# Upper bound on compositions refined per input color.
MAX_CANDIDATE_COMPOSITIONS = 128


def is_translucent_set(colors: Colors) -> bool:
    """Classify the material set using its mean RGB transmission distance."""
    return bool(colors.colors) and bool(np.mean([
        td for color in colors.colors.values() for td in color.td_channels
    ]) >= TRANSPARENT_TD_THRESHOLD_MM)


def composition_codes(labels: list, layer_count: int) -> list:
    """One canonical (sorted) code per composition of layer_count over labels.

    Exactly ``C(len(labels) + layer_count - 1, layer_count)`` entries.
    """
    return [
        "".join(combo)
        for combo in itertools.combinations_with_replacement(sorted(labels), layer_count)
    ]


def _unrank_ordering(letters: list[str], counts: list[int], rank: int, total: int) -> str:
    """The rank-th distinct ordering (lexicographic) of a multiset of letters.

    Removing one letter leaves total * count / remaining orderings (an exact
    integer identity for multinomial counts), so each step is O(len(letters)).
    """
    counts = list(counts)
    remaining = sum(counts)
    out = []
    for _ in range(remaining):
        for i, letter in enumerate(letters):
            if counts[i] == 0:
                continue
            block = total * counts[i] // remaining
            if rank < block:
                out.append(letter)
                counts[i] -= 1
                total = block
                remaining -= 1
                break
            rank -= block
    return "".join(out)


def distinct_permutations(code: str, cap: int = MAX_PERMS_PER_COMPOSITION) -> list:
    """All unique orderings of a code's letters in lexicographic order,
    deterministically capped.

    Above the cap, orderings are sampled evenly by rank so the cap stays
    representative rather than biased toward the lexicographic head; they are
    unranked directly instead of enumerating every permutation.
    """
    letters = sorted(set(code))
    counts = [code.count(letter) for letter in letters]
    total = math.factorial(len(code))
    for count in counts:
        total //= math.factorial(count)
    if total <= cap:
        ranks = range(total)
    else:
        ranks = sorted(set(np.linspace(0, total - 1, cap).round().astype(int).tolist()))
    return [_unrank_ordering(letters, counts, rank, total) for rank in ranks]


def _lab(rgb01: np.ndarray) -> np.ndarray:
    """Convert an (N, 3) RGB array in [0, 1] to CIELAB (N, 3)."""
    from skimage.color import rgb2lab

    return rgb2lab(np.asarray(rgb01, dtype=np.float64).reshape(-1, 1, 3)).reshape(-1, 3)


def _cap_distinct_compositions(
    pool: np.ndarray,
    ref_codes: list,
    rep_pen: np.ndarray,
    rep_raw: np.ndarray,
    cap: int,
) -> list:
    """Keep the best ``cap`` DISTINCT composition codes from a margin pool.

    Matrix padding repeats the final composition (495 compositions pad to
    506 cells); duplicate entries are ranked identically, so deduplicate by
    code before applying the cap. Ties keep index order (stable sort).
    """
    pool = np.asarray(pool)
    order = pool[np.argsort(np.minimum(rep_pen[pool], rep_raw[pool]), kind="stable")]
    chosen: dict = {}
    for j in order.tolist():
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

    ref_codes = code_matrix.to_numpy().ravel().tolist()
    ref_rgb01 = np.array(rgb_matrix.to_numpy().ravel().tolist(), dtype=np.float64) / 255.0
    ref_lab = _lab(ref_rgb01)

    inp_lab = _lab(np.array(input_colors, dtype=np.float64) / 255.0)

    perm_cache: dict = {}
    perm_lock = threading.Lock()

    def orderings(rep_code: str) -> tuple:
        # Blend every ordering of a composition once; reused by later inputs.
        with perm_lock:
            if rep_code not in perm_cache:
                codes = distinct_permutations(rep_code)
                rgb = np.array(codes_to_rgb(codes), dtype=np.float64)
                perm_cache[rep_code] = (codes, rgb, _lab(rgb / 255.0))
            return perm_cache[rep_code]

    def refine(i: int) -> tuple:
        lab_color = inp_lab[i]
        rep_pen = Color.perceptual_distance(lab_color, ref_lab)
        rep_raw = Color.perceptual_distance_raw(lab_color, ref_lab)
        pool = np.flatnonzero(
            (rep_pen <= rep_pen.min() + margin_delta_e) | (rep_raw <= rep_raw.min() + margin_delta_e)
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
        evaluated = 0
        for idx in pool:
            perms, perm_rgb, perm_lab = orderings(ref_codes[idx])
            if len(perm_rgb) > 1:
                perm_dists = Color.perceptual_distance(lab_color, perm_lab)
                evaluated += len(perms)
                local = int(np.argmin(perm_dists))
                if float(perm_dists[local]) < best_dist:
                    best_dist = float(perm_dists[local])
                    best_code = perms[local]
                    # Keep the same float domain as the stage-1 rgb it may
                    # replace; callers round to the image domain themselves.
                    best_rgb = tuple(float(v) for v in perm_rgb[local])
                # The stage-1 representative itself stays a candidate via the
                # first entry of its (sorted) permutation list.
        return best_code, best_rgb, evaluated

    # Inputs refine independently; numpy releases the GIL in the distance passes.
    with ThreadPoolExecutor(max_workers=worker_threads()) as pool_executor:
        refined = list(pool_executor.map(refine, range(len(input_colors))))

    logger.info(
        "Prune refinement: %d inputs, %d orderings evaluated",
        len(input_colors), sum(evaluated for _, _, evaluated in refined),
    )
    return [code for code, _, _ in refined], [rgb for _, rgb, _ in refined]
