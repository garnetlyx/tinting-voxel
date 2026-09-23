"""Parameter generation covers its ranges and is reproducible for a fixed seed."""
from hypothesis import given, settings
from hypothesis import strategies as st
from services.param_search_service import GridSearch, RandomSearch


@given(
    ranges=st.fixed_dictionaries({
        "a": st.lists(st.integers(0, 10), min_size=1, max_size=4),
        "b": st.lists(st.floats(0, 1, allow_nan=False, allow_infinity=False), min_size=1, max_size=3),
        "c": st.lists(st.integers(0, 5), min_size=1, max_size=2),
    })
)
@settings(max_examples=100)
def test_grid_search_completeness(ranges):
    """Property 5: GridSearch yields exactly product(len(range)) combinations with correct keys."""
    gs = GridSearch(mode="pixel", param_ranges=ranges)
    expected_total = 1
    for v in ranges.values():
        expected_total *= len(v)

    combos = list(gs.generate())
    assert len(combos) == expected_total, f"Expected {expected_total} combos, got {len(combos)}"
    assert gs.total() == expected_total

    expected_keys = set(ranges.keys())
    for combo in combos:
        assert set(combo.keys()) == expected_keys, f"Combo keys mismatch: {combo.keys()}"


# ---------------------------------------------------------------------------
# Property 6: Random search trial count
# Feature: param-search-optimizer, Property 6: Random search trial count
# ---------------------------------------------------------------------------

@given(n=st.integers(1, 200))
@settings(max_examples=100)
def test_random_search_trial_count(n):
    """Property 6: RandomSearch yields exactly n_trials combinations."""
    rs = RandomSearch(mode="pixel", n_trials=n)
    combos = list(rs.generate())
    assert len(combos) == n, f"Expected {n} trials, got {len(combos)}"
    assert rs.total() == n


# ---------------------------------------------------------------------------
# Property 7: Random search bounds containment
# Feature: param-search-optimizer, Property 7: Random search bounds containment
# ---------------------------------------------------------------------------

@given(n=st.integers(1, 50))
@settings(max_examples=100)
def test_random_search_bounds_containment(n):
    """Property 7: All sampled values are within their specified bounds."""
    bounds = {
        "max_colors": ("int", 4, 16),
        "color_threshold": ("float", 10.0, 100.0),
        "detail_size": ("float", 0.22, 0.82),
        "white_backing_layers": ("choice", [0, 1]),
    }
    rs = RandomSearch(mode="pixel", n_trials=n, param_bounds=bounds)
    for combo in rs.generate():
        assert 4 <= combo["max_colors"] <= 16
        assert 10.0 <= combo["color_threshold"] <= 100.0
        assert 0.22 <= combo["detail_size"] <= 0.82
        assert combo["white_backing_layers"] in (0, 1)


# ---------------------------------------------------------------------------
# Property 8: Random search reproducibility
# Feature: param-search-optimizer, Property 8: Random search reproducibility
# ---------------------------------------------------------------------------

@given(
    seed=st.integers(0, 2**31 - 1),
    n=st.integers(1, 50),
)
@settings(max_examples=100)
def test_random_search_reproducibility(seed, n):
    """Property 8: Same seed produces identical sequences."""
    rs1 = RandomSearch(mode="pixel", n_trials=n, seed=seed)
    rs2 = RandomSearch(mode="pixel", n_trials=n, seed=seed)
    combos1 = list(rs1.generate())
    combos2 = list(rs2.generate())
    assert combos1 == combos2, "Same seed must produce identical sequences"
