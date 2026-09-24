"""Printed backing material and thickness participate in color prediction."""
import numpy as np
import pytest

from core.blend_color import Colors, colors_key
from core.color_config import ColorConfig
from core.color_config import get_preset
from core.blend_models import codes_to_rgb_batch
from services.image_processor import _map_source_colors_to_blends
from services.print_stack import (
    PRINT_BACKGROUND_RGB,
    backing_suffix,
    build_print_stack,
    default_backing_label,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)
from services.stl_generator import compute_reference_matrices


BAMBU = Colors.from_configs(get_preset("bambu_cmyw"))


# ---------------------------------------------------------------- resolution

def test_backing_is_the_chosen_filament_or_the_one_closest_to_white():
    assert resolve_backing_label(BAMBU, 1) == 'W'
    assert resolve_backing_label(BAMBU, 1, 'M') == 'M'
    assert resolve_backing_label(BAMBU, 0, 'M') is None


def test_backing_filament_must_be_in_the_set():
    with pytest.raises(ValueError, match="Backing filament 'K' is not in this filament set"):
        resolve_backing_label(BAMBU, 3, 'K')


@pytest.mark.parametrize("preset, label", [
    ("bambu_cmywk", "W"), ("bambu_cmyw", "W"), ("clear_cmyw", "W"),
    # No white: the neutral grey, not the bright yellow RGB distance would pick.
    ("clear_cmyg", "G"),
])
def test_default_backing_is_the_filament_that_looks_closest_to_white(preset, label):
    assert default_backing_label(Colors.from_configs(get_preset(preset))) == label


def test_default_backing_for_custom_set_without_pure_white():
    custom = Colors.from_configs([
        ColorConfig(name='A', hex='#F5F0E8', transmission_distance=1.0),  # beige
        ColorConfig(name='B', hex='#101010', transmission_distance=1.0),  # near-black
        ColorConfig(name='C', hex='#2050A0', transmission_distance=1.0),
        ColorConfig(name='D', hex='#A02020', transmission_distance=1.0),
    ])
    assert resolve_backing_label(custom, 2) == 'A'


def test_backing_suffix_and_strip_roundtrip():
    suffix = backing_suffix('W', 3)
    assert suffix == 'WWW'
    code = 'CYMYYYYY' + suffix
    assert strip_backing_suffix(code, 'W', 3) == 'CYMYYYYY'
    # n=0 / no label: identity
    assert backing_suffix('W', 0) == ''
    assert strip_backing_suffix('CYMYYYYY', 'W', 0) == 'CYMYYYYY'


def test_backing_filaments_predict_actual_filament_layers_under_one_background():
    for label in "WM":
        codes, rgbs = _map_source_colors_to_blends(
            [(29, 30, 30)], BAMBU, 4, 0.08, backing_layers=3, backing_filament=label,
        )
        assert codes[0].endswith(label * 3)
        expected = codes_to_rgb_batch(codes, 0.08, colors_key(BAMBU), background_rgb=PRINT_BACKGROUND_RGB)
        np.testing.assert_array_equal(rgbs, np.round(expected).astype(int))
        np.testing.assert_allclose(expected, codes_to_rgb_batch(codes, 0.08, colors_key(BAMBU)), atol=0, rtol=0)


def test_print_stack_metadata_names_the_backing_filament():
    stack = build_print_stack(8, 0.08, 3, 'K')
    assert stack == {
        "opticalLayerCount": 8,
        "whiteBackingLayers": 3,
        "backingFilament": "K",
        "totalLayerCount": 11,
        "totalHeightMm": 0.88,
    }
    assert build_print_stack(8, 0.08, 0, 'K')["backingFilament"] is None


# ------------------------------------------------------------ simulation

def test_backing_layers_shift_simulated_color():
    """Thickness dependence: the same code changes as the backing grows."""
    key = colors_key(BAMBU)
    no_backing = codes_to_rgb_batch(['CYMYYYYY'], 0.08, key)[0]
    one_w = codes_to_rgb_batch(['CYMYYYYYW'], 0.08, key)[0]
    three_w = codes_to_rgb_batch(['CYMYYYYYWWW'], 0.08, key)[0]
    three_m = codes_to_rgb_batch(
        ['CYMYYYYYMMM'], 0.08, key, background_rgb=PRINT_BACKGROUND_RGB
    )[0]
    assert one_w != no_backing
    assert three_w != one_w
    assert three_m != three_w


def test_mapping_returns_full_stack_code_with_backing_suffix():
    codes, rgbs = _map_source_colors_to_blends(
        [(0x1D, 0x1E, 0x1E)], BAMBU, 8, 0.08, backing_layers=3,
    )
    assert codes[0].endswith('WWW')
    assert len(codes[0]) == 8 + 3
    # No backing: optical code only.
    codes0, _ = _map_source_colors_to_blends(
        [(0x1D, 0x1E, 0x1E)], BAMBU, 8, 0.08, backing_layers=0,
    )
    assert len(codes0[0]) == 8


def test_mapping_result_depends_on_backing_filament():
    """Backing changes the result when the front layers transmit enough light."""
    translucent = Colors.from_configs([
        ColorConfig(name=c.name, hex=c.hex, transmission_distance=2.0)
        for c in get_preset("bambu_cmyw")
    ])
    dark = (0x1D, 0x1E, 0x1E)
    codes_w, rgb_w = _map_source_colors_to_blends([dark], translucent, 8, 0.08, 3, 'W')
    codes_m, rgb_m = _map_source_colors_to_blends([dark], translucent, 8, 0.08, 3, 'M')
    assert codes_w[0].endswith('WWW')
    assert codes_m[0].endswith('MMM')
    assert not np.allclose(rgb_w, rgb_m)


def test_reference_matrices_backing_cache_isolation():
    """Different backing configs must not alias in the matrix cache."""
    m0 = compute_reference_matrices(4, 0.08, BAMBU, n_targets=3, backing_layers=0)
    m3 = compute_reference_matrices(4, 0.08, BAMBU, n_targets=3, backing_layers=3, backing_filament='W')
    mb = compute_reference_matrices(4, 0.08, BAMBU, n_targets=3, backing_layers=3, backing_filament='M')
    r0 = np.asarray(m0[1].iloc[0, 0], dtype=float)
    r3 = np.asarray(m3[1].iloc[0, 0], dtype=float)
    rb = np.asarray(mb[1].iloc[0, 0], dtype=float)
    assert not np.allclose(r0, r3)
    assert not np.allclose(r3, rb)


def test_zero_backing_has_no_hidden_filament_dependent_background():
    matrices = [
        compute_reference_matrices(4, 0.08, BAMBU, n_targets=3, backing_layers=0, backing_filament=label)
        for label in "WM"
    ]
    assert matrices[0][0].equals(matrices[1][0])
    assert matrices[0][1].equals(matrices[1][1])
    for code_matrix, rgb_matrix in matrices:
        code = code_matrix.iloc[0, 0]
        expected = codes_to_rgb_batch([code], 0.08, colors_key(BAMBU))[0]
        cell = np.asarray(rgb_matrix.iloc[0, 0], dtype=float)
        np.testing.assert_array_equal(cell, np.round(expected))


def test_normalize_backing_layers():
    assert normalize_backing_layers(None) == 3
    assert normalize_backing_layers(0) == 0
    assert normalize_backing_layers(-3) == 0
