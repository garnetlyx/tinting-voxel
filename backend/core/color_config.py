"""
Color configuration dataclass for N-color filament support.

Provides a clean interface for configuring custom filament colors
with name, hex color, and transmission distance properties.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ColorConfig:
    """
    Configuration for a single filament color.

    Attributes:
        name: Display name for the color (e.g., "Cyan", "Magenta")
        hex: Hex color code (e.g., "#00FFFF")
        transmission_distance: Beer-Lambert transmission distance parameter
            Controls how light passes through the material.
            Lower values = more opaque, Higher values = more translucent.
    """
    name: str
    hex: str
    transmission_distance: float
    alpha: float = 12.0
    k: float = 10.0  # Scattering coefficient (per-channel `k_c`)

    def __post_init__(self):
        """Validate color configuration."""
        self.name = self.name.strip() if self.name else self.name
        if not self.name:
            raise ValueError("Color name cannot be empty or whitespace-only")

        # Name must start with an ASCII letter (A-Z or a-z)
        # The first character becomes the blend code, which must be ASCII
        if not self.name or not self.name[0].isalpha() or not self.name[0].isascii():
            raise ValueError(
                f"Color name must start with an ASCII letter (A-Z, a-z): {self.name}. "
                f"The first character is used as the blend code identifier."
            )

        # Validate hex format: must be '#' followed by exactly 6 hex digits
        import re
        if not re.match(r'^#[0-9a-fA-F]{6}$', self.hex):
            raise ValueError(
                f"Invalid hex color format: {self.hex}. "
                f"Must be '#' followed by 6 hex digits (e.g., '#00FFFF')"
            )

        if self.transmission_distance <= 0:
            raise ValueError(
                f"Transmission distance must be positive: {self.transmission_distance}"
            )

        if self.alpha <= 0:
            raise ValueError(
                f"Alpha (absorption coefficient) must be positive: {self.alpha}"
            )

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


# Preset definitions for common filament configurations
BAMBU_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#3D79C6", transmission_distance=3.0, alpha=12.0, k=10.0),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=1.9, alpha=12.0, k=10.0),
    ColorConfig(name="Yellow", hex="#FFE665", transmission_distance=2.5, alpha=12.0, k=10.0),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2, alpha=12.0, k=10.0),
]

# Phase 6 Calibration (2026-03-07) - Derived from Black/White Dual Backing
# Note: transmission_distance here is the PRE-SCALED TD1S value adjusted by 1.48 * (TD)^0.2
BAMBU_CMYK_CALIBRATED_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#3D79C6", transmission_distance=1.70, alpha=8.08, k=8.13),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=2.22, alpha=8.08, k=8.42),
    ColorConfig(name="Yellow", hex="#FFE665", transmission_distance=4.15, alpha=8.08, k=3.73),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=5.48, alpha=8.08, k=12.39),
    ColorConfig(name="Key", hex="#0B0F0C", transmission_distance=2.21, alpha=8.08, k=17.65), # Black (K)
]

CLEAR_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#0089cd", transmission_distance=60.0, alpha=12.0, k=10.0),
    ColorConfig(name="Magenta", hex="#e75d4a", transmission_distance=100.0, alpha=12.0, k=10.0),
    ColorConfig(name="Yellow", hex="#f6d449", transmission_distance=70.0, alpha=12.0, k=10.0),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=200.0, alpha=12.0, k=10.0),
]


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """
    Get a preset color configuration by name.

    Args:
        name: Preset name ("bambu_cmyk", "bambu_cmyk_calibrated" or "clear_cmyk")

    Returns:
        List of ColorConfig or None if preset not found
    """
    if name is None:
        return None
    presets = {
        "bambu_cmyk": BAMBU_CMYK_PRESET,
        "bambu_cmyk_calibrated": BAMBU_CMYK_CALIBRATED_PRESET,
        "clear_cmyk": CLEAR_CMYK_PRESET,
    }
    return presets.get(name.lower())


def get_available_presets() -> List[str]:
    """Get list of available preset names."""
    return ["bambu_cmyk", "bambu_cmyk_calibrated", "clear_cmyk"]
