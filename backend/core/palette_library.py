"""
Curated color palette library for filament configurations.

Exposes the two supported built-in filament configurations for browsing.
"""
from dataclasses import dataclass
from typing import List, Optional

from core.color_config import ColorConfig, BAMBU_CMYW_PHASE6_PRESET, CLEAR_CMYWG_PRESET


@dataclass
class PaletteEntry:
    """A named palette in the library."""
    id: str
    name: str
    description: str
    colors: List[ColorConfig]


# Palette metadata references the canonical filament presets.
PALETTE_BAMBU_CMYW_PHASE6 = PaletteEntry(
    id="bambu_cmyw_phase6",
    name="Bambu CMYW Phase 6",
    description="Phase 6 calibrated Bambu Lab CMYW filament set for full-color printing",
    colors=BAMBU_CMYW_PHASE6_PRESET,  # Reference source-of-truth constant
)

PALETTE_CLEAR_CMYWG = PaletteEntry(
    id="clear_cmywg",
    name="Clear CMYWG",
    description="Translucent CMYWG filament set for light-diffusing prints",
    colors=CLEAR_CMYWG_PRESET,  # Reference source-of-truth constant
)

ALL_PALETTES: List[PaletteEntry] = [PALETTE_BAMBU_CMYW_PHASE6, PALETTE_CLEAR_CMYWG]


def get_palette(palette_id: str) -> Optional[PaletteEntry]:
    """Get a palette by its ID (case-insensitive). Returns a copy to prevent mutation."""
    if palette_id is None:
        return None
    palette_id_lower = palette_id.lower()
    for palette in ALL_PALETTES:
        if palette.id.lower() == palette_id_lower:
            # Return a deep copy to prevent mutation of global state
            from dataclasses import replace
            # Create copies of each ColorConfig to avoid shared references
            copied_colors = [replace(color) for color in palette.colors]
            return replace(palette, colors=copied_colors)
    return None
