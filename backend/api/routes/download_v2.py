"""
V2 Download endpoints with configurable filament colors.

Maintains backward compatibility while adding N-color support.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import Response

from api.error_handlers import handle_api_errors
from api.rate_limiter import limiter
from api.models import (
    DownloadSTLRequestV2,
    DownloadSVGSTLRequestV2,
    FilamentColorConfig,
    FilamentPreset,
    FilamentPresetInfo,
    FilamentPresetsResponse,
    PrintSettingsRequest,
)
from core.blend_color import Colors
from core.color_config import (
    BAMBU_CMYK_PRESET,
    BAMBU_CMYK_CALIBRATED_PRESET,
    BAMBU_CMYK_PHASE6_PRESET,
    BAMBU_CMYW_PHASE6_PRESET,
    CLEAR_CMYK_PRESET,
    ColorConfig,
    get_preset,
)
from services.print_settings_generator import generate_print_settings
from services.stl_generator import generate_stl_zip
from services.svg_stl_generator import generate_svg_stl_zip
from services.threemf_generator import generate_3mf, generate_svg_3mf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Downloads V2"])


def get_colors_from_request(
    filament_preset: Optional[FilamentPreset],
    filament_colors: Optional[List[FilamentColorConfig]]
) -> Colors:
    """
    Get Colors instance from request parameters.

    Priority: filament_colors > filament_preset > default CMYK

    Args:
        filament_preset: Optional preset name
        filament_colors: Optional list of custom color configs

    Returns:
        Colors instance
    """
    if filament_colors:
        # Use custom colors
        configs = [
            ColorConfig(
                name=fc.name,
                hex=fc.hex,
                transmission_distance=fc.transmission_distance,
                alpha=fc.alpha,
                k=fc.k,
                td_scale=fc.td_scale,
                td_gamma=fc.td_gamma,
            )
            for fc in filament_colors
        ]
        return Colors.from_configs(configs)

    if filament_preset:
        # Use preset
        preset_configs = get_preset(filament_preset.value)
        if preset_configs:
            return Colors.from_configs(preset_configs)

    # Fall back to the default image-preview Phase 6 CMYK preset (with Key/black)
    default_configs = get_preset(FilamentPreset.BAMBU_CMYK_PHASE6.value)
    return Colors.from_configs(default_configs) if default_configs else Colors()


@router.get("/filament-presets", response_model=FilamentPresetsResponse)
@limiter.limit("30/minute")
async def api_get_filament_presets(request: Request):
    """
    Get available filament presets.

    Returns list of presets with their color configurations.
    """
    presets = [
        FilamentPresetInfo(
            name="bambu_cmyk",
            display_name="Bambu CMYK",
            colors=[
                FilamentColorConfig(
                    name=c.name,
                    hex=c.hex,
                    transmission_distance=c.transmission_distance,
                    alpha=c.alpha,
                    k=c.k,
                    td_scale=c.td_scale,
                    td_gamma=c.td_gamma,
                )
                for c in BAMBU_CMYK_PRESET
            ]
        ),
        FilamentPresetInfo(
            name="clear_cmyk",
            display_name="Clear CMYK",
            colors=[
                FilamentColorConfig(
                    name=c.name,
                    hex=c.hex,
                    transmission_distance=c.transmission_distance,
                    alpha=c.alpha,
                    k=c.k,
                    td_scale=c.td_scale,
                    td_gamma=c.td_gamma,
                )
                for c in CLEAR_CMYK_PRESET
            ]
        ),
        FilamentPresetInfo(
            name="bambu_cmyk_calibrated",
            display_name="Bambu CMYK Calibrated",
            colors=[
                FilamentColorConfig(
                    name=c.name,
                    hex=c.hex,
                    transmission_distance=c.transmission_distance,
                    alpha=c.alpha,
                    k=c.k,
                    td_scale=c.td_scale,
                    td_gamma=c.td_gamma,
                )
                for c in BAMBU_CMYK_CALIBRATED_PRESET
            ]
        ),
        FilamentPresetInfo(
            name="bambu_cmyk_phase6",
            display_name="Bambu CMYK Phase 6",
            colors=[
                FilamentColorConfig(
                    name=c.name,
                    hex=c.hex,
                    transmission_distance=c.transmission_distance,
                    alpha=c.alpha,
                    k=c.k,
                    td_scale=c.td_scale,
                    td_gamma=c.td_gamma,
                )
                for c in BAMBU_CMYK_PHASE6_PRESET
            ]
        ),
        FilamentPresetInfo(
            name="bambu_cmyw_phase6",
            display_name="Bambu CMYW Phase 6",
            colors=[
                FilamentColorConfig(
                    name=c.name,
                    hex=c.hex,
                    transmission_distance=c.transmission_distance,
                    alpha=c.alpha,
                    k=c.k,
                    td_scale=c.td_scale,
                    td_gamma=c.td_gamma,
                )
                for c in BAMBU_CMYW_PHASE6_PRESET
            ]
        ),
    ]
    return FilamentPresetsResponse(presets=presets)


@router.post("/download-stl")
@limiter.limit("5/minute")
@handle_api_errors("generating STL v2")
async def api_download_stl_v2(request: Request, body: DownloadSTLRequestV2):
    """Generate and download ZIP file containing color-separated STL files (V2, configurable colors)."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    image_dimensions = body.imageDimensions.model_dump()

    zip_content = generate_stl_zip(
        color_blocks=color_blocks,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        base_plate_thickness=body.basePlateThickness or 0.0,
        double_sided=body.doubleSided,
        white_backing_layers=body.whiteBackingLayers,
    )

    logger.info(
        "Generated STL ZIP (v2, %d colors) for %d color blocks, %dx%d pixels",
        len(colors), len(color_blocks),
        image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=all_color_blocks.zip"}
    )


@router.post("/download-svg-stl")
@limiter.limit("5/minute")
@handle_api_errors("generating SVG STL v2")
async def api_download_svg_stl_v2(request: Request, body: DownloadSVGSTLRequestV2):
    """Generate and download ZIP file containing color-separated STL files (V2, SVG mode)."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    vector_results = [result.model_dump() for result in body.vectorResults]
    image_dimensions = body.imageDimensions.model_dump()

    zip_content = generate_svg_stl_zip(
        vector_results=vector_results,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        base_plate_thickness=body.basePlateThickness or 0.0,
        double_sided=body.doubleSided,
        white_backing_layers=body.whiteBackingLayers,
    )

    logger.info(
        "Generated STL ZIP (v2 SVG mode, %d colors) for %d color groups, %dx%d pixels",
        len(colors), len(vector_results),
        image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=all_color_blocks.zip"}
    )


@router.post("/download-3mf")
@limiter.limit("5/minute")
@handle_api_errors("generating 3MF")
async def api_download_3mf(request: Request, body: DownloadSTLRequestV2):
    """Generate and download a 3MF file with color-separated objects."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    image_dimensions = body.imageDimensions.model_dump()

    # Build label -> hex color map for visual colors in 3MF
    color_hex_map = {}
    if body.filamentColors:
        for fc in body.filamentColors:
            color_hex_map[fc.label] = fc.hex
    else:
        for label in colors.get_labels():
            color_hex_map[label] = colors[label].hex

    threemf_content = generate_3mf(
        color_blocks=color_blocks,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        base_plate_thickness=body.basePlateThickness or 0.0,
        color_hex_map=color_hex_map,
        double_sided=body.doubleSided,
        white_backing_layers=body.whiteBackingLayers,
    )

    logger.info(
        "Generated 3MF for %d color blocks, %dx%d pixels",
        len(color_blocks), image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=threemf_content,
        media_type="application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        headers={"Content-Disposition": "attachment; filename=color_blocks.3mf"}
    )


@router.post("/download-svg-3mf")
@limiter.limit("5/minute")
@handle_api_errors("generating SVG 3MF")
async def api_download_svg_3mf(request: Request, body: DownloadSVGSTLRequestV2):
    """Generate and download a 3MF file from SVG vector contours with color-separated objects."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    vector_results = [result.model_dump() for result in body.vectorResults]
    image_dimensions = body.imageDimensions.model_dump()

    color_hex_map = {}
    if body.filamentColors:
        for fc in body.filamentColors:
            color_hex_map[fc.label] = fc.hex
    else:
        for label in colors.get_labels():
            color_hex_map[label] = colors[label].hex

    threemf_content = generate_svg_3mf(
        vector_results=vector_results,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        base_plate_thickness=body.basePlateThickness or 0.0,
        color_hex_map=color_hex_map,
        double_sided=body.doubleSided,
        white_backing_layers=body.whiteBackingLayers,
    )

    logger.info(
        "Generated SVG 3MF for %d color groups, %dx%d pixels",
        len(vector_results), image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=threemf_content,
        media_type="application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        headers={"Content-Disposition": "attachment; filename=color_blocks.3mf"}
    )


@router.post("/print-settings")
@limiter.limit("10/minute")
@handle_api_errors("generating print settings")
async def api_print_settings(request: Request, body: PrintSettingsRequest):
    """Generate and download a JSON print settings file."""
    # Resolve filament colors from preset or custom config
    filament_colors_dicts = []
    preset_name = None

    if body.filamentColors:
        filament_colors_dicts = [
            {
                'name': fc.name,
                'hex': fc.hex,
                'transmission_distance': fc.transmission_distance,
            }
            for fc in body.filamentColors
        ]
    elif body.filamentPreset:
        preset_name = body.filamentPreset.value
        preset_configs = get_preset(preset_name)
        if preset_configs:
            filament_colors_dicts = [
                {
                    'name': c.name,
                    'hex': c.hex,
                    'transmission_distance': c.transmission_distance,
                }
                for c in preset_configs
            ]
    else:
        for c in BAMBU_CMYK_PRESET:
            filament_colors_dicts.append({
                'name': c.name,
                'hex': c.hex,
                'transmission_distance': c.transmission_distance,
            })
        preset_name = 'bambu_cmyk'

    image_dimensions = body.imageDimensions.model_dump()

    settings_json = generate_print_settings(
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        filament_colors=filament_colors_dicts,
        white_backing_layers=body.whiteBackingLayers,
        base_plate_thickness=body.basePlateThickness or 0.0,
        filament_preset=preset_name,
        double_sided=body.doubleSided,
    )

    logger.info("Generated print settings JSON")

    return Response(
        content=settings_json,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=print_settings.json"}
    )
