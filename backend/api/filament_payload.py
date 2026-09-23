"""
Shared resolution of filament configuration from request payloads.

Two entry shapes exist in the API:
- JSON-body routes pass typed `filamentPreset` / `filamentColors` fields.
- Multipart Form routes receive both as raw strings (colors as JSON text).

Both funnel through here to validate the selected source and resolve defaults.
"""
import json
import logging
from typing import Optional

from fastapi import HTTPException

from api.models import FilamentColorConfig, FilamentConfigMixin, FilamentPreset
from core.blend_color import Colors
from core.color_config import ColorConfig, get_preset
from core.stack_prune import is_translucent_set
from config.print_defaults import REGULAR_LAYER_HEIGHT_MM, TRANSPARENT_LAYER_HEIGHT_MM

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
    """Build the selected custom set, preset, or configured default set."""
    if filament_colors:
        configs = [
            ColorConfig(
                name=fc.name,
                hex=fc.hex,
                transmission_distance=fc.transmission_distance,
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

    return Colors()


def resolve_layer_height(layer_height: Optional[float], colors: Colors) -> float:
    """Only an omitted height uses the material set's TD-based default."""
    if layer_height is not None:
        return layer_height
    return TRANSPARENT_LAYER_HEIGHT_MM if is_translucent_set(colors) else REGULAR_LAYER_HEIGHT_MM
