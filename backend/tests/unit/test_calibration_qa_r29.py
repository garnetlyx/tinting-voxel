"""
QA Round 29 - ColorConfig NaN/Infinity Validation

Tests verify that ColorConfig properly rejects NaN and Infinity values
for scalar and per-channel transmission distances.

Bug IDs: QA-R29-01 through QA-R29-06
"""
import math
import pytest

from core.color_config import ColorConfig


def test_color_config_rejects_nan_transmission_distance():
    """
    QA-R29-01: ColorConfig accepts NaN transmission_distance.

    Uses <= 0 check which doesn't catch NaN. Should use math.isfinite()
    to properly validate all numeric parameters.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Nn]a[Nn]"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=float('nan'))


def test_color_config_rejects_inf_transmission_distance():
    """
    QA-R29-02: ColorConfig accepts Infinity transmission_distance.

    Same issue - <= 0 check doesn't catch Infinity.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Ii]nfinity"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=float('inf'))


def test_color_config_rejects_nan_channel():
    with pytest.raises(ValueError, match="finite"):
        ColorConfig("Test", "#FF0000", (1.0, float("nan"), 2.0))


def test_color_config_rejects_negative_inf_transmission_distance():
    """
    Additional: Negative Infinity should also be rejected.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Ii]nfinity"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=float('-inf'))


def test_color_config_accepts_valid_values():
    """
    Verify that valid values still work after adding finite checks.
    """
    c = ColorConfig(name="TestColor", hex="#00FF00", transmission_distance=2.5)
    assert c.transmission_distance == 2.5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
