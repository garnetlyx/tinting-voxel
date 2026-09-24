"""Exercise real small caches and the production warmup enumeration separately."""
from unittest.mock import Mock

import pytest

from core import color_config
from services import matrix_cache


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    from collections import OrderedDict
    monkeypatch.setattr(matrix_cache, '_MATRIX_CACHE', OrderedDict())


def test_warmup_populates_real_matrices_for_each_requested_height():
    from core.color_config import get_preset
    from core.blend_color import Colors
    preset = 'bambu_cmyw'
    assert matrix_cache.warmup_cache([preset], [2], [0.08, 0.12]) == 2
    for height in [0.08, 0.12]:
        colors = Colors.from_configs(get_preset(preset))
        code_matrix, rgb_matrix = matrix_cache.get_cached_matrices(colors, 2, height)
        assert code_matrix.size == 16
        assert rgb_matrix.shape == code_matrix.shape
        assert all(len(code) == 2 for code in code_matrix.values.flatten())
    assert matrix_cache.get_cache_stats()['size'] == 2


def test_default_warmup_visits_all_presets_and_layer_counts(monkeypatch):
    monkeypatch.setattr(color_config, 'get_available_presets', lambda: ['first', 'second'])
    compute = Mock()
    monkeypatch.setattr(matrix_cache, 'compute_and_cache_matrices', compute)
    assert matrix_cache.warmup_cache() == 4
    assert [call.args for call in compute.call_args_list] == [
        (preset, layers, 0.08)
        for preset in ['first', 'second'] for layers in [4, 5]
    ]


def test_warmup_continues_after_an_invalid_preset():
    from core.color_config import get_preset
    from core.blend_color import Colors
    assert matrix_cache.warmup_cache(['invalid', 'bambu_cmyw'], [2], [0.08]) == 1
    assert matrix_cache.get_cached_matrices(Colors.from_configs(get_preset('bambu_cmyw')), 2, 0.08) is not None



def test_default_backing_cache_matches_explicit_three_layers_only():
    from core.blend_color import Colors
    from core.color_config import get_preset
    from services.stl_generator import compute_reference_matrices
    colors = Colors.from_configs(get_preset("bambu_cmyw"))
    actual = compute_reference_matrices(2, 0.08, colors)
    default = matrix_cache.get_cached_matrices(colors, 2, 0.08)
    explicit = matrix_cache.get_cached_matrices(
        colors, 2, 0.08,
        backing_suffix="WWW", background_rgb=(255.0, 255.0, 255.0),
    )
    assert default is explicit
    assert default[0] is actual[0]
    assert default[1] is actual[1]
    assert matrix_cache.get_cached_matrices(
        colors, 2, 0.08,
        backing_suffix="W", background_rgb=(255.0, 255.0, 255.0),
    ) is None
    assert matrix_cache.get_cached_matrices(
        colors, 2, 0.08, backing_suffix="", background_rgb=None,
    ) is None



def test_td_channels_invalidate_cached_predictions_and_equal_channels_share_cache():
    from core.blend_color import Colors
    from core.color_config import ColorConfig
    from services.stl_generator import compute_reference_matrices

    def materials(cyan_td):
        return Colors.from_configs([
            ColorConfig("Cyan", "#3D79C6", cyan_td),
            ColorConfig("Magenta", "#B3356E", 0.5),
            ColorConfig("Yellow", "#FFE665", 0.6),
            ColorConfig("White", "#FFFFFF", 0.7),
        ])

    scalar = materials(0.4)
    compute_reference_matrices(2, 0.08, scalar)
    cached = matrix_cache.get_cached_matrices(scalar, 2, 0.08)
    assert cached is not None
    assert matrix_cache.get_cached_matrices(materials([0.4, 0.4, 0.4]), 2, 0.08) is cached
    assert matrix_cache.get_cached_matrices(materials([0.4, 0.6, 0.8]), 2, 0.08) is None


def test_requests_with_different_color_counts_share_one_matrix():
    from core.blend_color import Colors
    from core.color_config import get_preset
    from services.stl_generator import compute_reference_matrices

    colors = Colors.from_configs(get_preset("bambu_cmywk"))
    first = compute_reference_matrices(4, 0.08, colors, n_targets=3)
    assert compute_reference_matrices(4, 0.08, colors, n_targets=12)[0] is first[0]
    assert matrix_cache.get_cache_stats()['size'] == 1


def test_startup_warmup_serves_real_requests():
    from core.blend_color import Colors
    from core.color_config import get_preset
    from services.stl_generator import compute_reference_matrices

    assert matrix_cache.warmup_cache(['bambu_cmywk'], [4], [0.08]) == 1
    warmed = matrix_cache.get_cached_matrices(Colors.from_configs(get_preset('bambu_cmywk')), 4, 0.08)
    request = compute_reference_matrices(
        4, 0.08, Colors.from_configs(get_preset('bambu_cmywk')), n_targets=10, backing_layers=3,
    )
    assert request[0] is warmed[0]


def test_cache_stays_within_its_reference_budget(monkeypatch):
    """Large custom sets evict older entries by total references; the newest stays."""
    import pandas as pd

    from config.settings import settings
    from core.blend_color import Colors

    monkeypatch.setattr(settings, "matrix_cache_max_references", 10)
    colors = Colors.from_configs(color_config.get_preset("bambu_cmywk"))
    small = pd.DataFrame([["A"] * 4])
    large = pd.DataFrame([["A"] * 8])
    matrix_cache.set_cached_matrices(colors, 4, 0.08, small, small)
    matrix_cache.set_cached_matrices(colors, 5, 0.08, large, large)
    assert matrix_cache.get_cached_matrices(colors, 4, 0.08) is None
    assert matrix_cache.get_cache_stats()["references"] == 8
    too_large = pd.DataFrame([["A"] * 12])
    matrix_cache.set_cached_matrices(colors, 6, 0.08, too_large, too_large)
    assert matrix_cache.get_cached_matrices(colors, 6, 0.08) is not None
    assert matrix_cache.get_cache_stats()["size"] == 1
