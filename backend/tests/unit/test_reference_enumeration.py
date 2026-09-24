"""Distinct-color reference enumeration must match brute-force enumeration."""
import itertools

import numpy as np
import pandas as pd
import pytest

from core.blend_color import Colors, colors_key
from core.blend_models import codes_to_rgb_batch
from core.color_config import get_preset
from core.color_materials import Color
from core.stack_prune import composition_codes
from services.print_stack import PRINT_BACKGROUND_RGB, backing_suffix, resolve_backing_label
from services.stl_generator import _as_matrices, _distinct_reference_colors


def _brute_force(colors: Colors, codes: list[str], layer_height: float, suffix: str, boundary):
    """Every code with its 8-bit color, blended one list at a time."""
    rgbs = codes_to_rgb_batch(
        [code + suffix for code in codes], layer_height, colors_key(colors), background_rgb=boundary,
    )
    return [tuple(int(v) for v in np.clip(np.round(rgb), 0, 255)) for rgb in rgbs]


def _first_occurrences(codes: list[str], rgbs: list[tuple]) -> tuple[list[str], list[tuple]]:
    first: dict = {}
    for code, rgb in zip(codes, rgbs):
        first.setdefault(rgb, code)
    return list(first.values()), list(first.keys())


CASES = [
    ("bambu_cmywk", 5, 0.08, 3),
    ("bambu_cmyw", 6, 0.08, 0),
    ("clear_cmyw", 5, 0.84, 3),
]


@pytest.mark.parametrize("preset,layers,height,backing", CASES)
def test_full_enumeration_keeps_first_code_per_distinct_color(preset, layers, height, backing):
    colors = Colors.from_configs(get_preset(preset))
    suffix = backing_suffix(resolve_backing_label(colors, backing, "white"), backing)
    boundary = PRINT_BACKGROUND_RGB if suffix else None
    all_codes = ["".join(p) for p in itertools.product(colors.get_labels(), repeat=layers)]

    expected = _first_occurrences(all_codes, _brute_force(colors, all_codes, height, suffix, boundary))
    assert _distinct_reference_colors(colors, layers, height, suffix, boundary) == expected


def test_code_list_enumeration_keeps_list_order():
    colors = Colors.from_configs(get_preset("clear_cmyg"))
    compositions = composition_codes(colors.get_labels(), 6)
    suffix = backing_suffix(resolve_backing_label(colors, 3, "white"), 3)

    expected = _first_occurrences(compositions, _brute_force(colors, compositions, 0.84, suffix, PRINT_BACKGROUND_RGB))
    got = _distinct_reference_colors(colors, 6, 0.84, suffix, PRINT_BACKGROUND_RGB, code_list=compositions)
    assert got == expected


@pytest.mark.parametrize("preset,layers,height,backing", CASES)
def test_matching_representatives_equals_matching_every_code(preset, layers, height, backing):
    colors = Colors.from_configs(get_preset(preset))
    suffix = backing_suffix(resolve_backing_label(colors, backing, "white"), backing)
    boundary = PRINT_BACKGROUND_RGB if suffix else None
    all_codes = ["".join(p) for p in itertools.product(colors.get_labels(), repeat=layers)]
    all_rgbs = _brute_force(colors, all_codes, height, suffix, boundary)
    every_code = (pd.DataFrame([all_codes]), pd.DataFrame([all_rgbs]))
    representatives = _as_matrices(*_distinct_reference_colors(colors, layers, height, suffix, boundary))

    targets = np.random.default_rng(3).integers(0, 256, size=(40, 3)).tolist()
    expected_codes, expected_rgbs = Color.map_to_nearest_color(targets, *every_code)
    got_codes, got_rgbs = Color.map_to_nearest_color(targets, *representatives)
    assert got_codes == expected_codes
    assert [list(v) for v in got_rgbs] == [list(v) for v in expected_rgbs]
