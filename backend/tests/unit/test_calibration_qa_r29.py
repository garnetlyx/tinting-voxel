"""
QA Round 29 - ColorConfig NaN/Infinity Validation

Tests verify that ColorConfig properly rejects NaN and Infinity values
for all numeric parameters (transmission_distance, alpha, k, td_scale, td_gamma).

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


def test_color_config_rejects_nan_alpha():
    """
    QA-R29-03: ColorConfig accepts NaN alpha.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Nn]a[Nn]"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=1.0, alpha=float('nan'))


def test_color_config_rejects_nan_k():
    """
    QA-R29-04: ColorConfig accepts NaN k (scattering coefficient).
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Nn]a[Nn]"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=1.0, k=float('nan'))


def test_color_config_rejects_nan_td_scale():
    """
    QA-R29-05: ColorConfig accepts NaN td_scale.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Nn]a[Nn]"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=1.0, td_scale=float('nan'))


def test_color_config_rejects_nan_td_gamma():
    """
    QA-R29-06: ColorConfig accepts NaN td_gamma.
    """
    with pytest.raises(ValueError, match="[Ff]inite|[Nn]a[Nn]"):
        ColorConfig(name="Test", hex="#FF0000", transmission_distance=1.0, td_gamma=float('nan'))


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
    assert c.alpha == 12.0  # default
    assert c.k == 10.0  # default
    assert c.td_scale == 1.0  # default
    assert c.td_gamma == 1.0  # default


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
