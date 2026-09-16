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
    Configuration for a single filament color: name, hex, td, optional k,
    optional per-channel td_rgb.
    """
    name: str
    hex: str
    # Channel-neutral transmission distance (mm), the one composite TD a
    # filament carries. For scalar-form filaments this is the raw TD
    # reading remapped by td_scale/td_gamma (paper Eq. (2)); presets carry
    # the fitted provenance in comments below. User-entered values are
    # used literally (base-10: t = 10^(-d/td)) under neutral defaults.
    transmission_distance: float
    # Optional per-channel transmission distances (mm), [td_R, td_G, td_B].
    # Present on filaments characterized by staircase measurement:
    # the per-channel selectivity IS the td data. Absent -> scalar td form.
    # Same forward family either way; see core.blend_models._resolve_extinction.
    td_rgb: Optional[List[float]] = None
    # Optional pigment absorption gain; 0 blends as plain Beer-Lambert.
    # Calibrated presets carry fitted values, customs default to 0.
    k: float = 0.0
    # Scalar-form capture compensation (paper Eqs. (1)-(2)), used only when
    # td_rgb is absent: td_eff = td_scale * td**td_gamma,
    # mu_ch = alpha_s/td_eff + k*A_ch. Neutral defaults (alpha_s = ln 10,
    # td_scale = td_gamma = 1) degrade to ln(10)/td + k*A_ch.
    alpha_s: float = 2.302585092994046
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

        if self.td_rgb is not None:
            if len(self.td_rgb) != 3:
                raise ValueError(
                    f"td_rgb must be exactly 3 per-channel distances [R, G, B], got {self.td_rgb}"
                )
            for ch, td_ch in enumerate(self.td_rgb):
                if not math.isfinite(td_ch) or td_ch <= 0:
                    raise ValueError(
                        f"td_rgb channel {'RGB'[ch]} must be positive and finite, got {td_ch}"
                    )

        if not math.isfinite(self.k) or self.k < 0:
            raise ValueError(
                f"k (scattering coefficient) must be non-negative and finite, got {self.k}"
            )

        for field_name in ("alpha_s", "td_scale", "td_gamma"):
            value = getattr(self, field_name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(
                    f"{field_name} must be positive and finite, got {value}"
                )

    @property
    def label(self) -> str:
        """Get single-character label from name."""
        return self.name[0].upper()


# Bambu CMYWK / CMYW presets: paper PLATE-06-H2C-A standard fit
# (data/results/PLATE-06-H2C-paper-matrix/runs/A-standard/fitted_params.json,
# IJAMT Table 3 row "PLATE-06-H2C-A"). td = raw scalar TD readings
# (td_reference); k = fitted per-color capture-compensation k_c. The
# remap triple is the exact algebraic composition of the fitted remap
# (s_td = 4.7782, gamma_td = 0.1636) with the preset remap the engine run
# applied on top of it (1.48 * x^0.20), collapsed into one power law
# (paper Eq. (2) form): td_scale = 1.48 * 4.7782**0.20,
# td_gamma = 0.1636 * 0.20. Forward: mu_ch = alpha_s/(s*td^g) + k_c*A_ch
# reproduces the research engine's PLATE-06-H2C-A predictions exactly
# (780/780 cells within CSV rounding). Calibrated at layer height 0.32 mm.
_ALPHA_S_A = 2.2292
_TD_SCALE_A = 2.023552983514602
_TD_GAMMA_A = 0.03272
BAMBU_CMYWK_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#3D79C6", transmission_distance=2.0, k=3.4996,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=2.9, k=4.3077,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="Yellow",  hex="#FFE665", transmission_distance=5.0, k=3.6572,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="White",   hex="#FFFFFF", transmission_distance=6.1, k=6.3168,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="Key",     hex="#0B0F0C", transmission_distance=0.1, k=23.1863,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
]

# Same CMYW channels without Key (legacy 4-color option).
BAMBU_CMYW_PHASE6_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#3D79C6", transmission_distance=2.0, k=3.4996,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="Magenta", hex="#B3356E", transmission_distance=2.9, k=4.3077,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="Yellow",  hex="#FFE665", transmission_distance=5.0, k=3.6572,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
    ColorConfig(name="White",   hex="#FFFFFF", transmission_distance=6.1, k=6.3168,
                 alpha_s=_ALPHA_S_A, td_scale=_TD_SCALE_A, td_gamma=_TD_GAMMA_A),
]

# Clear CMYG preset (stained-glass track), P07-def staircase characterization
# (research crossval_report.json, plate CMYG print 1, default print config).
# td_rgb = staircase-measured per-channel TDs (Ziro cyan / Isanmate pink /
# Sunlu yellow / Panchroma grey); scalar td = channel arithmetic mean
# (fallback/display). k = 0: the per-channel TDs already carry all measured
# attenuation (mu_ch = ln10/td_ch, the same unified formula as every other
# filament). Grey is a translucent dark — same material model as the rest.
# Provenance: data/results/clear-plate-crossval/ P07-def.
CLEAR_CMYG_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#5489B4", transmission_distance=4.667418746800521,
                 td_rgb=[1.039647851596278, 4.661388851322945, 8.301219537482337], k=0.0),
    ColorConfig(name="Magenta", hex="#DE5740", transmission_distance=6.31945243505504,
                 td_rgb=[12.871171884721239, 2.3866487980887325, 3.700536622355147], k=0.0),
    ColorConfig(name="Yellow",  hex="#DDC465", transmission_distance=10.074691453694577,
                 td_rgb=[15.128418453030553, 12.290455104172315, 2.8052008038808633], k=0.0),
    ColorConfig(name="Grey",    hex="#9A9D9C", transmission_distance=1.7030698349645412,
                 td_rgb=[2.226964674889777, 1.688155998369564, 1.1940888316342828], k=0.0),
]

# Clear CMYW preset (stained-glass track), P08-kxa staircase characterization
# (research crossval_report.json, PLATE-08-KX-A, same physical batch as the
# plate-08 certification reference). td_rgb = staircase-measured per-channel
# TDs; scalar td = channel mean. k = 0.
# Provenance: data/results/clear-plate-crossval/ P08-kxa.
CLEAR_CMYW_PRESET: List[ColorConfig] = [
    ColorConfig(name="Cyan",    hex="#4C72A0", transmission_distance=2.6582813347278655,
                 td_rgb=[1.3490352079515975, 2.5371501740106988, 4.088658622221301], k=0.0),
    ColorConfig(name="Magenta", hex="#CE5E53", transmission_distance=5.252097918532708,
                 td_rgb=[11.210903332862577, 2.0338821311932, 2.511508291542347], k=0.0),
    ColorConfig(name="Yellow",  hex="#D8B695", transmission_distance=14.295863422405146,
                 td_rgb=[22.124563670499846, 15.378730904545765, 5.384295692169828], k=0.0),
    ColorConfig(name="White",   hex="#D9D6C5", transmission_distance=18.02000330638548,
                 td_rgb=[17.949461574719358, 18.902845340687115, 17.207703003749966], k=0.0),
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
