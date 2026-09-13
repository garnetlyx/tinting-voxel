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
    preset = 'bambu_cmyw_phase6'
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
    assert matrix_cache.warmup_cache(['invalid', 'bambu_cmyw_phase6'], [2], [0.08]) == 1
    assert matrix_cache.get_cached_matrices(Colors.from_configs(get_preset('bambu_cmyw_phase6')), 2, 0.08) is not None
