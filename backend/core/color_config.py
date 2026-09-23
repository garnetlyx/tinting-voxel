"""
Color configuration dataclass for N-color filament support.

Provides a clean interface for configuring custom filament colors
with name, hex color, and transmission distance properties.
"""
import math
from dataclasses import dataclass
from typing import List, Optional


TransmissionDistance = float | tuple[float, float, float]


def normalize_transmission_distance(value) -> TransmissionDistance:
    """Validate one TD value, either a scalar or three RGB channel distances."""
    from numbers import Real

    def channel(number):
        if isinstance(number, bool) or not isinstance(number, Real):
            raise ValueError("Transmission distance must be a number or three RGB numbers")
        number = float(number)
        if not math.isfinite(number) or number <= 0:
            raise ValueError("Transmission distance must be positive and finite")
        return number

    if isinstance(value, (list, tuple)):
        if len(value) != 3:
            raise ValueError("Transmission distance must contain exactly three RGB channels")
        return tuple(channel(number) for number in value)
    return channel(value)


@dataclass
class ColorConfig:
    """A filament's display color and transmission distance in millimetres."""
    name: str
    hex: str
    transmission_distance: TransmissionDistance

    def __post_init__(self):
        import re

        self.name = self.name.strip() if self.name else self.name
        if not self.name:
            raise ValueError("Color name cannot be empty or whitespace-only")
        if not self.name[0].isalpha() or not self.name[0].isascii():
            raise ValueError(
                f"Color name must start with an ASCII letter (A-Z, a-z): {self.name}. "
                "The first character is used as the blend code identifier."
            )
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.hex):
            raise ValueError(f"Invalid hex color format: {self.hex}")
        self.transmission_distance = normalize_transmission_distance(self.transmission_distance)

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


BAMBU_CMYWK_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(name='Cyan', hex='#3D79C6', transmission_distance=(0.14985206885995866, 0.2158019588968432, 0.34470002110761544)),
    ColorConfig(name='Magenta', hex='#B3356E', transmission_distance=(0.25394517301625485, 0.11741231747797068, 0.16740952089338004)),
    ColorConfig(name='Yellow', hex='#FFE665', transmission_distance=(0.24453692139115935, 0.4161395063139576, 0.11645416645362061)),
    ColorConfig(name='White', hex='#FFFFFF', transmission_distance=(0.18080214399292235, 0.18110183709219985, 0.17340438182840498)),
    ColorConfig(name='Key', hex='#0B0F0C', transmission_distance=(0.11902961051255159, 0.09501141308426139, 0.09724992232345757)),
]

BAMBU_CMYW_PHASE6_PRESET: List[ColorConfig] = [
    color for color in BAMBU_CMYWK_PHASE6_PRESET if color.label != "K"
]

CLEAR_CMYG_PRESET: List[ColorConfig] = [
    ColorConfig(name='Cyan', hex='#5489B4', transmission_distance=(1.039647851596278, 4.661388851322945, 8.301219537482337)),
    ColorConfig(name='Magenta', hex='#DE5740', transmission_distance=(12.871171884721239, 2.3866487980887325, 3.700536622355147)),
    ColorConfig(name='Yellow', hex='#DDC465', transmission_distance=(15.128418453030553, 12.290455104172315, 2.8052008038808633)),
    ColorConfig(name='Grey', hex='#9A9D9C', transmission_distance=(2.226964674889777, 1.688155998369564, 1.1940888316342828)),
]

CLEAR_CMYW_PRESET: List[ColorConfig] = [
    ColorConfig(name='Cyan', hex='#4C72A0', transmission_distance=(1.3490352079515975, 2.5371501740106988, 4.088658622221301)),
    ColorConfig(name='Magenta', hex='#CE5E53', transmission_distance=(11.210903332862577, 2.0338821311932, 2.511508291542347)),
    ColorConfig(name='Yellow', hex='#D8B695', transmission_distance=(22.124563670499846, 15.378730904545765, 5.384295692169828)),
    ColorConfig(name='White', hex='#D9D6C5', transmission_distance=(17.949461574719358, 18.902845340687115, 17.207703003749966)),
]

PRESETS = {
    "bambu_cmywk_phase6": BAMBU_CMYWK_PHASE6_PRESET,
    "bambu_cmyw_phase6": BAMBU_CMYW_PHASE6_PRESET,
    "clear_cmyg": CLEAR_CMYG_PRESET,
    "clear_cmyw": CLEAR_CMYW_PRESET,
}

PRESET_DISPLAY_NAMES = {
    "bambu_cmywk_phase6": "Bambu CMYWK",
    "bambu_cmyw_phase6": "Bambu CMYW",
    "clear_cmyg": "Clear CMYG",
    "clear_cmyw": "Clear CMYW",
}


def get_preset(name: str) -> Optional[List[ColorConfig]]:
    """Resolve a canonical preset ID; unknown IDs are not remapped."""
    return PRESETS.get(name)


def get_available_presets() -> List[str]:
    """Return all supported built-in presets."""
    return list(PRESETS)
