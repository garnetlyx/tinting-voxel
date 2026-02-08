"""
Curated color palette library for filament configurations.

Provides a collection of pre-configured filament palettes organized by
category (standard, artistic, specialty) for users to browse and apply.
"""
from dataclasses import dataclass
from typing import List, Optional

from core.color_config import ColorConfig, BAMBU_CMYK_PRESET, CLEAR_CMYK_PRESET


@dataclass
class PaletteEntry:
    """A named palette in the library."""
    id: str
    name: str
    description: str
    category: str
    colors: List[ColorConfig]


# Standard CMYK palettes - reference source-of-truth presets from color_config
PALETTE_BAMBU_CMYK = PaletteEntry(
    id="bambu_cmyk",
    name="Bambu CMYK",
    description="Standard Bambu Lab CMYK filament set for full-color printing",
    category="standard",
    colors=BAMBU_CMYK_PRESET,  # Reference source-of-truth constant
)

PALETTE_CLEAR_CMYK = PaletteEntry(
    id="clear_cmyk",
    name="Clear CMYK",
    description="Translucent CMYK filament set for light-diffusing prints",
    category="standard",
    colors=CLEAR_CMYK_PRESET,  # Reference source-of-truth constant
)

# Extended CMYK with black
PALETTE_CMYKW_BLACK = PaletteEntry(
    id="cmykw_black",
    name="CMYK + Black",
    description="Full CMYK plus black for deeper shadows and contrast",
    category="standard",
    colors=[
        ColorConfig(name="Cyan", hex="#0086D6", transmission_distance=3.0),
        ColorConfig(name="Magenta", hex="#EC008C", transmission_distance=1.9),
        ColorConfig(name="Yellow", hex="#F4EE2A", transmission_distance=2.5),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
        ColorConfig(name="Black", hex="#1A1A1A", transmission_distance=0.5),
    ],
)

# Artistic palettes
PALETTE_EARTH_TONES = PaletteEntry(
    id="earth_tones",
    name="Earth Tones",
    description="Warm natural colors for landscape and nature prints",
    category="artistic",
    colors=[
        ColorConfig(name="Terracotta", hex="#C04000", transmission_distance=2.0),
        ColorConfig(name="Olive", hex="#6B8E23", transmission_distance=3.5),
        ColorConfig(name="Sand", hex="#C2B280", transmission_distance=5.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

PALETTE_OCEAN = PaletteEntry(
    id="ocean",
    name="Ocean",
    description="Cool blues and greens for underwater and marine themes",
    category="artistic",
    colors=[
        ColorConfig(name="Deep Blue", hex="#003366", transmission_distance=1.5),
        ColorConfig(name="Teal", hex="#008080", transmission_distance=4.0),
        ColorConfig(name="Aqua", hex="#00CED1", transmission_distance=8.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

PALETTE_SUNSET = PaletteEntry(
    id="sunset",
    name="Sunset",
    description="Warm gradient from red to gold for sunset-themed prints",
    category="artistic",
    colors=[
        ColorConfig(name="Ruby", hex="#9B1B30", transmission_distance=1.5),
        ColorConfig(name="Orange", hex="#FF6B35", transmission_distance=3.0),
        ColorConfig(name="Gold", hex="#FFD700", transmission_distance=4.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

PALETTE_PASTEL = PaletteEntry(
    id="pastel",
    name="Pastel",
    description="Soft pastel shades for gentle, muted artwork",
    category="artistic",
    colors=[
        ColorConfig(name="Pink", hex="#FFB6C1", transmission_distance=6.0),
        ColorConfig(name="Lavender", hex="#E6E6FA", transmission_distance=8.0),
        ColorConfig(name="Mint", hex="#98FB98", transmission_distance=7.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=10.0),
    ],
)

# Specialty palettes
PALETTE_MONOCHROME = PaletteEntry(
    id="monochrome",
    name="Monochrome",
    description="Grayscale palette for black-and-white lithophanes",
    category="specialty",
    colors=[
        ColorConfig(name="Black", hex="#1A1A1A", transmission_distance=0.5),
        ColorConfig(name="Gray", hex="#808080", transmission_distance=3.0),
        ColorConfig(name="Light Gray", hex="#C0C0C0", transmission_distance=5.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

PALETTE_NEON = PaletteEntry(
    id="neon",
    name="Neon",
    description="Bright fluorescent colors for high-visibility prints",
    category="specialty",
    colors=[
        ColorConfig(name="Neon Green", hex="#39FF14", transmission_distance=5.0),
        ColorConfig(name="Hot Pink", hex="#FF69B4", transmission_distance=4.0),
        ColorConfig(name="Electric Blue", hex="#7DF9FF", transmission_distance=6.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

PALETTE_FOREST = PaletteEntry(
    id="forest",
    name="Forest",
    description="Deep greens and browns for woodland and botanical prints",
    category="artistic",
    colors=[
        ColorConfig(name="Forest Green", hex="#228B22", transmission_distance=2.5),
        ColorConfig(name="Brown", hex="#8B4513", transmission_distance=1.8),
        ColorConfig(name="Leaf Green", hex="#90EE90", transmission_distance=5.0),
        ColorConfig(name="White", hex="#FFFFFF", transmission_distance=7.2),
    ],
)

# All palettes in order
ALL_PALETTES: List[PaletteEntry] = [
    PALETTE_BAMBU_CMYK,
    PALETTE_CLEAR_CMYK,
    PALETTE_CMYKW_BLACK,
    PALETTE_EARTH_TONES,
    PALETTE_OCEAN,
    PALETTE_SUNSET,
    PALETTE_PASTEL,
    PALETTE_MONOCHROME,
    PALETTE_NEON,
    PALETTE_FOREST,
]

# Category descriptions
CATEGORIES = {
    "standard": "Standard CMYK printing palettes",
    "artistic": "Creative palettes for themed artwork",
    "specialty": "Special-purpose filament combinations",
}


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


def get_palettes_by_category(category: str) -> List[PaletteEntry]:
    """Get all palettes in a category. Returns copies to prevent mutation."""
    from dataclasses import replace
    result = []
    for palette in ALL_PALETTES:
        if palette.category == category:
            # Create copies of each ColorConfig to avoid shared references
            copied_colors = [replace(color) for color in palette.colors]
            result.append(replace(palette, colors=copied_colors))
    return result


def get_all_categories() -> List[str]:
    """Get all unique category names."""
    return list(CATEGORIES.keys())
