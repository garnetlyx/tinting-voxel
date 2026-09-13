"""
Shared resolution of filament configuration from request payloads.

Two entry shapes exist in the API:
- JSON-body routes pass typed `filamentPreset` / `filamentColors` fields.
- Multipart Form routes receive both as raw strings (colors as JSON text).

Both funnel through here so validation and preset-vs-colors priority are
defined exactly once. Priority: filamentColors > filamentPreset > built-in
default (Phase 6 CMYW).
"""
import json
import logging
from typing import Optional

from fastapi import HTTPException

from api.models import FilamentColorConfig, FilamentConfigMixin, FilamentPreset
from core.blend_color import Colors
from core.color_config import BAMBU_CMYWK_PHASE6_PRESET, ColorConfig, get_preset

logger = logging.getLogger(__name__)


def parse_filament_form_payload(
    filament_preset: Optional[str],
    filament_colors: Optional[str],
) -> tuple[Optional[FilamentPreset], Optional[list[FilamentColorConfig]]]:
    """Parse and validate raw Form-string filament fields."""
    parsed_preset = None
    parsed_colors = None

    if filament_preset:
        try:
            parsed_preset = FilamentPreset(filament_preset)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid filament preset: {filament_preset}. "
                    f"Valid presets: {', '.join(p.value for p in FilamentPreset)}"
                ),
            ) from exc

    if filament_colors:
        try:
            colors_data = json.loads(filament_colors)
        except (json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filamentColors JSON: {str(exc)}",
            ) from exc
        try:
            parsed_colors = [FilamentColorConfig.model_validate(item) for item in colors_data]
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filamentColors format: {str(exc)}",
            ) from exc

    try:
        validated = FilamentConfigMixin(
            filamentPreset=parsed_preset,
            filamentColors=parsed_colors,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return validated.filamentPreset, validated.filamentColors


def get_colors_from_request(
    filament_preset: Optional[FilamentPreset],
    filament_colors: Optional[list[FilamentColorConfig]],
) -> Colors:
    """Build a Colors instance from typed request fields.

    Priority: filament_colors > filament_preset > default Phase 6 CMYW.
    """
    if filament_colors:
        configs = [
            ColorConfig(
                name=fc.name,
                hex=fc.hex,
                transmission_distance=fc.transmission_distance,
                alpha=fc.alpha,
                k=fc.k,
                td_rgb=fc.td_rgb,
                td_neutral=fc.td_neutral,
                td_scale=fc.td_scale,
                td_gamma=fc.td_gamma,
            )
            for fc in filament_colors
        ]
        return Colors.from_configs(configs)

    if filament_preset:
        preset_configs = get_preset(filament_preset.value)
        if preset_configs:
            return Colors.from_configs(preset_configs)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown filament preset: {filament_preset.value}",
        )

    # Fall back to the default Phase 6 CMYWK preset
    return Colors.from_configs(BAMBU_CMYWK_PHASE6_PRESET)
