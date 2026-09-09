"""
Color configuration dataclass for N-color filament support.

Provides a clean interface for configuring custom filament colors
with name, hex color, and transmission distance properties.
"""
import math
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
        k_rgb: Optional per-channel scattering coefficients (k_R, k_G, k_B).
            If provided, overrides k for per-channel scattering calculation.
            Allows modeling channel-selective scattering (e.g., Cyan reflects R).
    """
    name: str
    hex: str
    transmission_distance: float
    alpha: float = 12.0
    k: float = 10.0  # Scattering coefficient (fallback when k_rgb not provided)
    k_rgb: Optional[tuple] = None  # Per-channel scattering (k_R, k_G, k_B)
    td_rgb: Optional[tuple] = None  # Measured per-channel TD (td_R, td_G, td_B), mm
    td_scale: float = 1.0
    td_gamma: float = 1.0

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

        if not math.isfinite(self.transmission_distance) or self.transmission_distance <= 0:
            raise ValueError(
                f"Transmission distance must be positive and finite, got {self.transmission_distance}"
            )

        if not math.isfinite(self.alpha) or self.alpha <= 0:
            raise ValueError(
                f"Alpha (absorption coefficient) must be positive and finite, got {self.alpha}"
            )

        if not math.isfinite(self.k) or self.k < 0:
            raise ValueError(
                f"k (scattering coefficient) must be non-negative and finite, got {self.k}"
            )

        if self.td_rgb is not None:
            if len(self.td_rgb) != 3:
                raise ValueError(
                    f"td_rgb must be a 3-tuple (td_R, td_G, td_B), got {self.td_rgb}"
                )
            for i, td_ch in enumerate(self.td_rgb):
                if not math.isfinite(td_ch) or td_ch <= 0:
                    raise ValueError(
                        f"td_rgb[{i}] must be finite and > 0, got {td_ch}"
                    )
        if self.k_rgb is not None:
            if len(self.k_rgb) != 3:
                raise ValueError(
                    f"k_rgb must be a 3-tuple (k_R, k_G, k_B), got {self.k_rgb}"
                )
            for i, k_ch in enumerate(self.k_rgb):
                if not math.isfinite(k_ch):
                    raise ValueError(
                        f"k_rgb[{i}] must be finite, got {k_ch}"
                    )

        if not math.isfinite(self.td_scale) or self.td_scale <= 0:
            raise ValueError(f"TD scale must be positive and finite, got {self.td_scale}")

        if not math.isfinite(self.td_gamma) or self.td_gamma <= 0:
            raise ValueError(f"TD gamma must be positive and finite, got {self.td_gamma}")

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


# Phase 6 CMYW calibration.
BAMBU_CMYW_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(
        name="Cyan",
        hex="#3D79C6",
        transmission_distance=2.0,
        alpha=8.08,
        k=8.13,
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Magenta",
        hex="#B3356E",
        transmission_distance=2.9,
        alpha=8.08,
        k=8.42,
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Yellow",
        hex="#FFE665",
        transmission_distance=5.0,
        alpha=8.08,
        k=3.73,
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="White",
        hex="#FFFFFF",
        transmission_distance=6.1,
        alpha=8.08,
        k=12.39,
        td_scale=1.48,
        td_gamma=0.20,
    ),
]

# Clear filament parameters from staircase v2 calibration (2026-07-17).
# Source: staircase v2 calibration (2026-07-17), staircase_report_v2.json
# Hex = WB-corrected thickest-step color; td/k = least-squares fit of the
# hybrid_per_color_k decay rate (alpha/td + k*A_ch) to the measured per-channel
# rates ln(10)/td_ch (thin-range fit, d <= 3mm). Clear filaments have negligible
# neutral scattering, so td saturates at the 200.0 cap and color separation is
# carried by k. Grey (Panchroma) has no staircase yet: hex/td are TD1S values.
# See docs/CLEAR_CALIBRATION.md "Preset Update" for derivation and residuals.
CLEAR_CMYWG_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#4C72A0", transmission_distance=200.0, alpha=12.0, k=1.93),  # Ziro Light Cyan Clear
    ColorConfig(name="Magenta", hex="#CE5E53", transmission_distance=200.0, alpha=12.0, k=1.44),  # iSANMATE Light Pink
    ColorConfig(name="Yellow", hex="#D8B695", transmission_distance=200.0, alpha=12.0, k=0.67),  # Sunlu Transparent Yellow
    ColorConfig(name="White", hex="#D9D6C5", transmission_distance=110.4, alpha=12.0, k=0.11),  # Kingroon Transparent PLA
    ColorConfig(name="Grey", hex="#676563", transmission_distance=7.3, alpha=12.0, k=10.0),  # Panchroma (staircase pending)
]

PRESETS = {
    "bambu_cmyw_phase6": BAMBU_CMYW_PHASE6_PRESET,
    "clear_cmywg": CLEAR_CMYWG_PRESET,
}

PRESET_DISPLAY_NAMES = {
    "bambu_cmyw_phase6": "Bambu CMYW Phase 6",
    "clear_cmywg": "Clear CMYWG",
}


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """Resolve a canonical preset ID; unknown IDs are not remapped."""
    return PRESETS.get(name)


def get_available_presets() -> List[str]:
    """Return all supported built-in presets."""
    return list(PRESETS)
