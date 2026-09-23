"""
Curated color palette library for filament configurations.

Exposes the two supported built-in filament configurations for browsing.
"""
from dataclasses import dataclass
from typing import List, Optional

from core.color_config import (
    ColorConfig,
    BAMBU_CMYWK_PRESET,
    BAMBU_CMYW_PRESET,
    CLEAR_CMYG_PRESET,
    CLEAR_CMYW_PRESET,
)


@dataclass
class PaletteEntry:
    """A named palette in the library."""
    id: str
    name: str
    description: str
    colors: List[ColorConfig]


# Palette metadata references the canonical filament presets.
PALETTE_BAMBU_CMYWK = PaletteEntry(
    id="bambu_cmywk",
    name="Bambu CMYWK",
    description="Calibrated Bambu Lab CMYWK filament set for full-color printing with true black",
    colors=BAMBU_CMYWK_PRESET,  # Reference source-of-truth constant
)

PALETTE_BAMBU_CMYW = PaletteEntry(
    id="bambu_cmyw",
    name="Bambu CMYW",
    description="Calibrated Bambu Lab CMYW filament set for full-color printing",
    colors=BAMBU_CMYW_PRESET,  # Reference source-of-truth constant
)

PALETTE_CLEAR_CMYW = PaletteEntry(
    id="clear_cmyw",
    name="Clear CMYW",
    description="Translucent CMYW filament set for stained-glass prints",
    colors=CLEAR_CMYW_PRESET,  # Reference source-of-truth constant
)

PALETTE_CLEAR_CMYG = PaletteEntry(
    id="clear_cmyg",
    name="Clear CMYG",
    description="Translucent CMYG filament set (staircase per-channel TDs) for stained-glass prints",
    colors=CLEAR_CMYG_PRESET,  # Reference source-of-truth constant
)

ALL_PALETTES: List[PaletteEntry] = [
    PALETTE_BAMBU_CMYWK,
    PALETTE_BAMBU_CMYW,
    PALETTE_CLEAR_CMYG,
    PALETTE_CLEAR_CMYW,
]


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
