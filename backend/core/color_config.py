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


# Preset definitions for common filament configurations
BAMBU_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#3D79C6", transmission_distance=3.0, alpha=12.0, k=10.0),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=1.9, alpha=12.0, k=10.0),
    ColorConfig(name="Yellow", hex="#FFE665", transmission_distance=2.5, alpha=12.0, k=10.0),
    ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2, alpha=12.0, k=10.0),
]

# Replay benchmark winner (2026-03-07).
# Uses raw TD1S measurements plus a learned td_scale * td^td_gamma remap and
# per-color k values. This is the strongest production-facing candidate in
# docs/CALIBRATION.md because it improves real-plate replay without collapsing
# transfer on the ramp/pair benchmarks.
BAMBU_CMYK_CALIBRATED_PRESET: List[ColorConfig] = [
    ColorConfig(
        name="Cyan",
        hex="#3D79C6",
        transmission_distance=2.0,
        alpha=5.751822945330163,
        k=1.2085100532667932,
        td_scale=1.0056869820712098,
        td_gamma=0.4543363851088494,
    ),
    ColorConfig(
        name="Magenta",
        hex="#B3356E",
        transmission_distance=2.9,
        alpha=5.751822945330163,
        k=0.35481383708372416,
        td_scale=1.0056869820712098,
        td_gamma=0.4543363851088494,
    ),
    ColorConfig(
        name="Yellow",
        hex="#FFE665",
        transmission_distance=5.0,
        alpha=5.751822945330163,
        k=8.401071443503248,
        td_scale=1.0056869820712098,
        td_gamma=0.4543363851088494,
    ),
    ColorConfig(
        name="White",
        hex="#FFFFFF",
        transmission_distance=6.1,
        alpha=5.751822945330163,
        k=6.523686193460801,
        td_scale=1.0056869820712098,
        td_gamma=0.4543363851088494,
    ),
    ColorConfig(
        name="Key",
        hex="#0B0F0C",
        transmission_distance=0.1,
        alpha=5.751822945330163,
        k=5.440433103311526,
        td_scale=1.0056869820712098,
        td_gamma=0.4543363851088494,
    ),
]

# Phase 6 B/W backing calibration (2026-03-07).
# Uses physically-ordered k values derived from black/white backing dual-calibration.
# These k values follow the correct physical ordering: K > W > M > C > Y.
# See docs/CALIBRATION.md "Phase 6" section for full derivation.
BAMBU_CMYK_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(
        name="Cyan",
        hex="#3D79C6",
        transmission_distance=2.0,  # TD1S sensor value
        alpha=8.08,  # scatter_alpha from Phase 6
        k=8.13,  # Per-color scattering coefficient (Phase 6)
        td_scale=1.48,  # TD1S power-law scaling
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Magenta",
        hex="#B3356E",
        transmission_distance=2.9,  # TD1S sensor value
        alpha=8.08,
        k=8.42,  # Phase 6 k value
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Yellow",
        hex="#FFE665",
        transmission_distance=5.0,  # TD1S sensor value
        alpha=8.08,
        k=3.73,  # Phase 6 k value (most translucent)
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="White",
        hex="#FFFFFF",
        transmission_distance=6.1,  # TD1S sensor value
        alpha=8.08,
        k=12.39,  # Phase 6 k value (high TiO₂ scattering)
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Key",
        hex="#0B0F0C",
        transmission_distance=0.1,  # TD1S sensor value (near-zero for black)
        alpha=8.08,
        k=17.65,  # Phase 6 k value (near-perfect opacity)
        td_scale=1.48,
        td_gamma=0.20,
    ),
]

# Phase 6 image-preview variant without K.
# Keeps the same Phase 6 CMYW parameters while removing the black channel so
# image mapping stays comparable to the legacy 4-color workflows.
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
CLEAR_CMYK_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#4C72A0", transmission_distance=200.0, alpha=12.0, k=1.93),  # Ziro Light Cyan Clear
    ColorConfig(name="Magenta", hex="#CE5E53", transmission_distance=200.0, alpha=12.0, k=1.44),  # iSANMATE Light Pink
    ColorConfig(name="Yellow", hex="#D8B695", transmission_distance=200.0, alpha=12.0, k=0.67),  # Sunlu Transparent Yellow
    ColorConfig(name="White", hex="#D9D6C5", transmission_distance=110.4, alpha=12.0, k=0.11),  # Kingroon Transparent PLA
    ColorConfig(name="Grey", hex="#676563", transmission_distance=7.3, alpha=12.0, k=10.0),  # Panchroma (staircase pending)
]

# 4-color clear filament subsets for 4-extruder printers.
# CMYG: primary mixing with translucent grey for dark tones (main calibration set).
CLEAR_CMYG_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#4C72A0", transmission_distance=200.0, alpha=12.0, k=1.93),
    ColorConfig(name="Magenta", hex="#CE5E53", transmission_distance=200.0, alpha=12.0, k=1.44),
    ColorConfig(name="Yellow", hex="#D8B695", transmission_distance=200.0, alpha=12.0, k=0.67),
    ColorConfig(name="Grey", hex="#676563", transmission_distance=7.3, alpha=12.0, k=10.0),
]

# CMYW: primary mixing with clear white as transparent substrate (validation set).
CLEAR_CMYW_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan", hex="#4C72A0", transmission_distance=200.0, alpha=12.0, k=1.93),
    ColorConfig(name="Magenta", hex="#CE5E53", transmission_distance=200.0, alpha=12.0, k=1.44),
    ColorConfig(name="Yellow", hex="#D8B695", transmission_distance=200.0, alpha=12.0, k=0.67),
    ColorConfig(name="White", hex="#D9D6C5", transmission_distance=110.4, alpha=12.0, k=0.11),
]

# Experimental per-channel k preset (2026-03-10).
# Uses per-channel scattering coefficients (k_R, k_G, k_B) to model
# channel-selective scattering behavior identified in error analysis.
#
# Key observations from docs/CALIBRATION.md:
# - Cyan R channel reflects (negative absorption) → low k_R
# - Magenta G channel absorbs strongly → high k_G
# - Yellow B channel absorbs strongly → high k_B, low k_R/k_G
#
# Note: This is an experimental preset. Values need calibration optimization.
BAMBU_CMYK_PER_CHANNEL_K_PRESET: List[ColorConfig] = [
    ColorConfig(
        name="Cyan",
        hex="#3D79C6",
        transmission_distance=2.0,
        alpha=8.08,
        k=8.13,  # Fallback scalar k
        k_rgb=(2.0, 10.0, 12.0),  # R reflects (low), G/B absorb (moderate-high)
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Magenta",
        hex="#B3356E",
        transmission_distance=2.9,
        alpha=8.08,
        k=8.42,
        k_rgb=(8.0, 15.0, 6.0),  # G absorbs strongly (high), R/B moderate
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Yellow",
        hex="#FFE665",
        transmission_distance=5.0,
        alpha=8.08,
        k=3.73,
        k_rgb=(1.0, 2.0, 10.0),  # B absorbs (high), R/G reflect (low)
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="White",
        hex="#FFFFFF",
        transmission_distance=6.1,
        alpha=8.08,
        k=12.39,
        k_rgb=(12.39, 12.39, 12.39),  # Uniform TiO₂ scattering
        td_scale=1.48,
        td_gamma=0.20,
    ),
    ColorConfig(
        name="Key",
        hex="#0B0F0C",
        transmission_distance=0.1,
        alpha=8.08,
        k=17.65,
        k_rgb=(17.65, 17.65, 17.65),  # Near-perfect opacity
        td_scale=1.48,
        td_gamma=0.20,
    ),
]


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """
    Get a preset color configuration by name.

    Args:
        name: Preset name ("bambu_cmyk", "bambu_cmyk_calibrated",
              "bambu_cmyk_phase6", "bambu_cmyw_phase6",
              "bambu_cmyk_per_channel_k", or "clear_cmyk")

    Returns:
        List of ColorConfig or None if preset not found
    """
    if name is None:
        return None
    normalized = name.lower()
    alias_map = {
        "bambu": "bambu_cmyk",
        "clear": "clear_cmyk",
    }
    presets = {
        "bambu_cmyk": BAMBU_CMYK_PRESET,
        "bambu_cmyk_calibrated": BAMBU_CMYK_CALIBRATED_PRESET,
        "bambu_cmyk_phase6": BAMBU_CMYK_PHASE6_PRESET,
        "bambu_cmyw_phase6": BAMBU_CMYW_PHASE6_PRESET,
        "bambu_cmyk_per_channel_k": BAMBU_CMYK_PER_CHANNEL_K_PRESET,
        "clear_cmyk": CLEAR_CMYK_PRESET,
        "clear_cmyg": CLEAR_CMYG_PRESET,
        "clear_cmyw": CLEAR_CMYW_PRESET,
    }
    return presets.get(alias_map.get(normalized, normalized))


def get_available_presets() -> List[str]:
    """
    Get list of available preset names.
    
    Returns only Phase 6 presets (current production presets).
    Archived presets are still accessible via get_preset() but hidden from UI.
    """
    return [
        "bambu_cmyk_phase6",
        "bambu_cmyw_phase6",
    ]


def get_archived_presets() -> List[str]:
    """
    Get list of archived preset names.
    
    These presets are still functional but hidden from the UI.
    Useful for testing, comparison, or backward compatibility.
    """
    return [
        "bambu_cmyk",
        "bambu_cmyk_calibrated",
        "bambu_cmyk_per_channel_k",
        "clear_cmyk",
    ]
