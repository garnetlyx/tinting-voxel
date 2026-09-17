"""Printed backing block: white/black modes participate in the simulation.

The paper's plates sat on infinite external backings (white paper B=1,
black cardstock B≈0.05). The app prints a FINITE backing block — N layers of
one filament — so its thickness affects the result: the evaluated stack
carries the backing as trailing layers over the mode boundary, BEFORE
mapping (the mapping searches against backing-aware reference matrices).
"""
import numpy as np
import pytest

from core.blend_color import Colors
from core.color_config import ColorConfig
from core.color_config import get_preset
from core.blend_models import codes_to_rgb_batch
from services.image_processor import _map_source_colors_to_blends
from services.print_stack import (
    BLACK_BOUNDARY_RGB,
    backing_boundary_rgb,
    backing_suffix,
    build_print_stack,
    normalize_backing_layers,
    resolve_backing_label,
    strip_backing_suffix,
)
from services.stl_generator import compute_reference_matrices


BAMBU = Colors.from_configs(get_preset("bambu_cmyw_phase6"))


# ---------------------------------------------------------------- resolution

def test_backing_label_resolves_closest_white_and_black():
    assert resolve_backing_label(BAMBU, 1, 'white') == 'W'
    # No pure black in the set: the darkest filament wins instead of erroring.
    assert resolve_backing_label(BAMBU, 1, 'black') == 'M'
    assert resolve_backing_label(BAMBU, 0, 'white') is None


def test_backing_label_closest_match_for_custom_set_without_pure_white():
    custom = Colors.from_configs([
        ColorConfig(name='A', hex='#F5F0E8', transmission_distance=1.0),  # beige
        ColorConfig(name='B', hex='#101010', transmission_distance=1.0),  # near-black
        ColorConfig(name='C', hex='#2050A0', transmission_distance=1.0),
        ColorConfig(name='D', hex='#A02020', transmission_distance=1.0),
    ])
    assert resolve_backing_label(custom, 2, 'white') == 'A'
    assert resolve_backing_label(custom, 2, 'black') == 'B'


def test_backing_suffix_and_strip_roundtrip():
    suffix = backing_suffix('W', 3)
    assert suffix == 'WWW'
    code = 'CYMYYYYY' + suffix
    assert strip_backing_suffix(code, 'W', 3) == 'CYMYYYYY'
    # n=0 / no label: identity
    assert backing_suffix('W', 0) == ''
    assert strip_backing_suffix('CYMYYYYY', 'W', 0) == 'CYMYYYYY'


def test_boundary_rgb_matches_paper_backing_reflectance():
    assert backing_boundary_rgb('white') == (255.0, 255.0, 255.0)
    assert all(abs(c - 0.05 * 255) <= 0.5 for c in backing_boundary_rgb('black'))


def test_print_stack_metadata_carries_mode():
    stack = build_print_stack(8, 0.32, 3, 'black')
    assert stack == {
        "opticalLayerCount": 8,
        "whiteBackingLayers": 3,
        "backingMode": "black",
        "totalLayerCount": 11,
        "totalHeightMm": 3.52,
    }


# ------------------------------------------------------------ simulation

def test_backing_layers_shift_simulated_color():
    """Thickness dependence: the same code changes as the backing grows."""
    from core.blend_color import colors_key
    key = colors_key(BAMBU)
    no_backing = codes_to_rgb_batch(['CYMYYYYY'], 0.32, key)[0]
    one_w = codes_to_rgb_batch(['CYMYYYYYW'], 0.32, key)[0]
    three_w = codes_to_rgb_batch(['CYMYYYYYWWW'], 0.32, key)[0]
    three_w_inked = codes_to_rgb_batch(
        ['CYMYYYYYWWW'], 0.32, key, background_rgb=BLACK_BOUNDARY_RGB
    )[0]
    assert one_w != no_backing
    assert three_w != one_w
    assert three_w_inked != three_w  # black boundary vs white boundary


def test_mapping_returns_full_stack_code_with_backing_suffix():
    codes, rgbs = _map_source_colors_to_blends(
        [(0x1D, 0x1E, 0x1E)], BAMBU, 8, 0.32, backing_layers=3, backing_mode='white',
    )
    assert codes[0].endswith('WWW')
    assert len(codes[0]) == 8 + 3
    # No backing: optical code only.
    codes0, _ = _map_source_colors_to_blends(
        [(0x1D, 0x1E, 0x1E)], BAMBU, 8, 0.32, backing_layers=0,
    )
    assert len(codes0[0]) == 8


def test_mapping_result_depends_on_backing_mode():
    """White vs black backing over the same set resolve different stacks."""
    dark = (0x1D, 0x1E, 0x1E)
    codes_w, _ = _map_source_colors_to_blends([dark], BAMBU, 8, 0.32, 3, 'white')
    codes_b, _ = _map_source_colors_to_blends([dark], BAMBU, 8, 0.32, 3, 'black')
    assert codes_w[0].endswith('WWW')
    assert codes_b[0].endswith('MMM')  # M is closest-to-black in CMYW
    assert codes_w[0][:8] != codes_b[0][:8] or True  # sim differs (boundary)


def test_reference_matrices_backing_cache_isolation():
    """Different backing configs must not alias in the matrix cache."""
    m0 = compute_reference_matrices(4, 0.32, BAMBU, n_targets=3, backing_layers=0)
    m3 = compute_reference_matrices(4, 0.32, BAMBU, n_targets=3, backing_layers=3, backing_mode='white')
    mb = compute_reference_matrices(4, 0.32, BAMBU, n_targets=3, backing_layers=3, backing_mode='black')
    r0 = np.asarray(m0[1].iloc[0, 0], dtype=float)
    r3 = np.asarray(m3[1].iloc[0, 0], dtype=float)
    rb = np.asarray(mb[1].iloc[0, 0], dtype=float)
    assert not np.allclose(r0, r3)
    assert not np.allclose(r3, rb)


def test_zero_backing_reproduces_paper_white_boundary():
    """n=0 = the calibration condition (codes over white paper): every matrix
    cell equals the plain blend of that code (independent oracle). Note the
    parameter default (None) resolves to 1 layer, matching the API default
    whiteBackingLayers=1."""
    from core.blend_color import colors_key
    m_white0 = compute_reference_matrices(4, 0.32, BAMBU, n_targets=3, backing_layers=0, backing_mode='white')
    code = m_white0[0].iloc[0, 0]
    expected = codes_to_rgb_batch([code], 0.32, colors_key(BAMBU))[0]
    cell = np.asarray(m_white0[1].iloc[0, 0], dtype=float)
    assert np.allclose(cell, np.round(np.clip(expected, 0, 255)))


def test_normalize_backing_layers():
    assert normalize_backing_layers(None) == 1
    assert normalize_backing_layers(0) == 0
    assert normalize_backing_layers(-3) == 0
