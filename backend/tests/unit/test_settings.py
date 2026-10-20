"""Settings validation: the forced-oversize hard cap must stay above the budget."""
import pytest
from pydantic import ValidationError

from config.settings import Settings


def test_hard_cap_below_budget_is_rejected():
    """A cap below the budget would void the ceiling (PR review P2): the
    guard's budget fast-path used to return before the cap check, so
    estimates between the two slipped through. Refuse the combination."""
    with pytest.raises(ValidationError, match="heavy_memory_hard_cap_mb"):
        Settings(heavy_memory_budget_mb=3072.0, heavy_memory_hard_cap_mb=1024.0)


def test_hard_cap_at_or_above_budget_is_accepted():
    assert Settings(heavy_memory_budget_mb=3072.0, heavy_memory_hard_cap_mb=3072.0)
    assert Settings(heavy_memory_budget_mb=3072.0, heavy_memory_hard_cap_mb=6144.0)
