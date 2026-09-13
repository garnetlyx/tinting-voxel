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
    Configuration for a single filament color: name, hex, td, optional k.
    """
    name: str
    hex: str
    # Channel-neutral transmission distance (mm), the one composite TD a
    # filament carries. Preset provenance: bambu = exact fold of the Phase-6
    # fitted scatter (ln10 * td_scale * td_td1s**td_gamma / alpha_s); clear =
    # staircase per-channel arithmetic mean. User-entered values are used
    # literally (base-10: t = 10^(-d/td)).
    transmission_distance: float
    # Optional pigment absorption gain; 0 blends as plain Beer-Lambert.
    # Calibrated presets carry fitted values, customs default to 0.
    k: float = 0.0

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

        if not math.isfinite(self.k) or self.k < 0:
            raise ValueError(
                f"k (scattering coefficient) must be non-negative and finite, got {self.k}"
            )



    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


# Bambu CMYWK / CMYW presets.
# td = exact algebraic fold of the Phase-6 fitted scatter term into a single
# base-10 transmission distance: td = ln(10) * td_scale * td_td1s**td_gamma
# / alpha_s with alpha_s=8.08, td_scale=1.48, td_gamma=0.20 over the TD1S
# readings (C 2.0 / M 2.9 / Y 5.0 / W 6.1 / K 0.1). The fitted per-color k
# values (dual-backing plate fit, physically ordered K > W > M > C > Y) are
# kept as-is. Blending this set is bit-identical to the retired
# hybrid_per_color_k_td1s_gamma model. Re-measure and replace with hardware
# photometer values when available.
BAMBU_CMYWK_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#3D79C6", transmission_distance=0.48447574859816506, k=8.13),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=0.5218499460436025, k=8.42),
    ColorConfig(name="Yellow",  hex="#FFE665", transmission_distance=0.5819156593127012, k=3.73),
    ColorConfig(name="White",   hex="#FFFFFF", transmission_distance=0.6055249051606083, k=12.39),
    ColorConfig(name="Key",     hex="#0B0F0C", transmission_distance=0.26611297079931917, k=17.65),
]

# Phase 6 CMYW without Key (legacy 4-color option); same folded values.
BAMBU_CMYW_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#3D79C6", transmission_distance=0.48447574859816506, k=8.13),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=0.5218499460436025, k=8.42),
    ColorConfig(name="Yellow",  hex="#FFE665", transmission_distance=0.5819156593127012, k=3.73),
    ColorConfig(name="White",   hex="#FFFFFF", transmission_distance=0.6055249051606083, k=12.39),
]

# Clear CMYW preset (stained-glass track).
# td = arithmetic mean of the staircase-measured per-channel TDs (thin-range
# fits, staircase-KX batch; per-channel originals live in the research repo —
# e.g. Ziro cyan (1.04, 4.66, 8.30) -> 4.7). k = 0: the staircase round-trip
# measurement already accounts for all attenuation. Grey is deliberately not
# part of this preset (physically opaque; brand-name "translucent" not
#withstanding).
#   Cyan:    #5489B4 (Ziro Light Cyan Clear)      td mean 4.7
#   Magenta: #DE5740 (iSANMATE Light Pink)        td mean 6.3
#   Yellow:  #DDC465 (Sunlu Transparent Yellow)  td mean 10.1
#   White:   #D9D6C5 (Kingroon Transparent PLA)   td mean 18.0
CLEAR_CMYW_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#5489B4", transmission_distance=4.7,  k=0.0),
    ColorConfig(name="Magenta", hex="#DE5740", transmission_distance=6.3,  k=0.0),
    ColorConfig(name="Yellow",  hex="#DDC465", transmission_distance=10.1, k=0.0),
    ColorConfig(name="White",   hex="#D9D6C5", transmission_distance=18.0, k=0.0),
]

PRESETS = {
    "bambu_cmywk_phase6": BAMBU_CMYWK_PHASE6_PRESET,
    "bambu_cmyw_phase6": BAMBU_CMYW_PHASE6_PRESET,
    "clear_cmyw": CLEAR_CMYW_PRESET,
}

PRESET_DISPLAY_NAMES = {
    "bambu_cmywk_phase6": "Bambu CMYWK",
    "bambu_cmyw_phase6": "Bambu CMYW",
    "clear_cmyw": "Clear CMYW",
}


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """Resolve a canonical preset ID; unknown IDs are not remapped."""
    return PRESETS.get(name)


def get_available_presets() -> List[str]:
    """Return all supported built-in presets."""
    return list(PRESETS)
