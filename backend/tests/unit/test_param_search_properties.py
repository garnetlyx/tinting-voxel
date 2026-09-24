"""Pattern search visits every grid point exactly once, whatever the scores."""
import math

from hypothesis import given, settings
from hypothesis import strategies as st

from services.param_search_service import SEARCH_SPACES, PatternSearch, SearchSpace


@st.composite
def spaces(draw):
    axes = {}
    coarse = {}
    for name in draw(st.lists(st.sampled_from("abc"), min_size=1, max_size=3, unique=True)):
        values = tuple(sorted(draw(st.sets(st.integers(0, 50), min_size=1, max_size=6))))
        axes[name] = values
        coarse[name] = tuple(sorted(draw(st.sets(st.sampled_from(values), min_size=1))))
    return SearchSpace(axes=axes, coarse=coarse, diagonal=draw(st.booleans()))


@given(space=spaces(), data=st.data())
@settings(max_examples=100, deadline=None)
def test_every_grid_point_is_visited_once_despite_failures(space, data):
    search = PatternSearch(space)
    visited = []
    while (params := search.next()) is not None:
        assert set(params) == set(space.axes)
        assert all(params[name] in values for name, values in space.axes.items())
        failed = data.draw(st.booleans())
        search.record(params, None if failed else data.draw(st.floats(0, 100)))
        visited.append(tuple(params[name] for name in space.axes))
    assert len(visited) == len(set(visited)) == math.prod(len(values) for values in space.axes.values())


@given(space=spaces(), data=st.data())
@settings(max_examples=100, deadline=None)
def test_recorded_current_settings_are_never_revisited(space, data):
    search = PatternSearch(space)
    current = {name: data.draw(st.sampled_from(values)) for name, values in space.axes.items()}
    search.record(current, 1.0)
    while (params := search.next()) is not None:
        assert params != current
        search.record(params, data.draw(st.floats(0, 100)))


def test_served_spaces_have_their_lattice_on_the_grid():
    for space in SEARCH_SPACES.values():
        assert list(space.axes) == list(space.coarse)
        for name, values in space.axes.items():
            assert list(values) == sorted(set(values))
            assert set(space.coarse[name]) <= set(values)
