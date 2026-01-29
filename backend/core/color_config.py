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

    def __post_init__(self):
        """Validate color configuration."""
        if not self.name:
            raise ValueError("Color name cannot be empty")

        # Validate hex format
        hex_value = self.hex.lstrip('#')
        if len(hex_value) != 6:
            raise ValueError(f"Invalid hex color format: {self.hex}")
        try:
            int(hex_value, 16)
        except ValueError:
            raise ValueError(f"Invalid hex color format: {self.hex}")

        if self.transmission_distance <= 0:
            raise ValueError(
                f"Transmission distance must be positive: {self.transmission_distance}"
            )

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


# Preset definitions for common filament configurations
BAMBU_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#0086D6", transmission_distance=3.0),
    ColorConfig(name="Magenta", hex="#EC008C", transmission_distance=1.9),
    ColorConfig(name="Yellow", hex="#F4EE2A", transmission_distance=2.5),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
]

CLEAR_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#0089cd", transmission_distance=60.0),
    ColorConfig(name="Magenta", hex="#e75d4a", transmission_distance=100.0),
    ColorConfig(name="Yellow", hex="#f6d449", transmission_distance=70.0),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=200.0),
]


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """
    Get a preset color configuration by name.

    Args:
        name: Preset name ("bambu_cmyk" or "clear_cmyk")

    Returns:
        List of ColorConfig or None if preset not found
    """
    presets = {
        "bambu_cmyk": BAMBU_CMYK_PRESET,
        "clear_cmyk": CLEAR_CMYK_PRESET,
    }
    return presets.get(name.lower())


def get_available_presets() -> List[str]:
    """Get list of available preset names."""
    return ["bambu_cmyk", "clear_cmyk"]
