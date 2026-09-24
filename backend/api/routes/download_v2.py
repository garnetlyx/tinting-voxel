"""
V2 Download endpoints with configurable filament colors.

Uses the shared material configuration for all exports.
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from api.error_handlers import handle_api_errors
from api.rate_limiter import limiter
from api.models import (
    DownloadSTLRequestV2,
    DownloadSVGSTLRequestV2,
    FilamentColorConfig,
    FilamentPresetInfo,
    FilamentPresetsResponse,
    PrintSettingsRequest,
)
from core.color_config import (
    PRESETS,
    PRESET_DISPLAY_NAMES,
)
from services.print_settings_generator import generate_print_settings
from config.settings import settings
from services.image_processor import MAX_PROCESSING_DIMENSION
from config.print_defaults import (
    DEFAULT_FILAMENT_PRESET, DEFAULT_BACKING_LAYERS,
    REGULAR_LAYER_HEIGHT_MM, TRANSPARENT_LAYER_HEIGHT_MM,
)
from core.stack_prune import TRANSPARENT_TD_THRESHOLD_MM

from services.stl_generator import generate_stl_zip
from services.svg_stl_generator import generate_svg_stl_zip
from services.threemf_generator import generate_3mf, generate_svg_3mf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Downloads V2"])


@router.get("/filament-presets", response_model=FilamentPresetsResponse)
@limiter.limit("30/minute")
async def api_get_filament_presets(request: Request):
    """
    Get available filament presets.

    Returns list of presets with their color configurations.
    """
    presets = [
        FilamentPresetInfo(
            name=name,
            display_name=PRESET_DISPLAY_NAMES[name],
            colors=[FilamentColorConfig(
                name=c.name, hex=c.hex,
                transmission_distance=c.transmission_distance,
            ) for c in configs],
        )
        for name, configs in PRESETS.items()
    ]
    return FilamentPresetsResponse(
        presets=presets,
        defaults={
            "filament_preset": DEFAULT_FILAMENT_PRESET,
            "backing_layers": DEFAULT_BACKING_LAYERS,
            "regular_layer_height_mm": REGULAR_LAYER_HEIGHT_MM,
            "transparent_layer_height_mm": TRANSPARENT_LAYER_HEIGHT_MM,
            "max_model_cells": settings.max_model_cells,
            "max_model_side_px": MAX_PROCESSING_DIMENSION,
        },
        transparency={"td_threshold_mm": TRANSPARENT_TD_THRESHOLD_MM, "aggregation": "mean"},
    )


@router.post("/download-stl")
@limiter.limit("5/minute")
@handle_api_errors("generating STL v2")
async def api_download_stl_v2(request: Request, body: DownloadSTLRequestV2):
    """Generate and download ZIP file containing color-separated STL files (V2, configurable colors)."""
    colors = body.resolved_colors
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    image_dimensions = body.imageDimensions.model_dump()

    zip_content = await run_in_threadpool(
        generate_stl_zip,
        color_blocks=color_blocks,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
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
    colors = body.resolved_colors
    vector_results = [result.model_dump() for result in body.vectorResults]
    image_dimensions = body.imageDimensions.model_dump()

    zip_content = await run_in_threadpool(
        generate_svg_stl_zip,
        vector_results=vector_results,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
        detail_size=body.detailSize,
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
    colors = body.resolved_colors
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

    threemf_content = await run_in_threadpool(
        generate_3mf,
        color_blocks=color_blocks,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        color_hex_map=color_hex_map,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
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
    colors = body.resolved_colors
    vector_results = [result.model_dump() for result in body.vectorResults]
    image_dimensions = body.imageDimensions.model_dump()

    color_hex_map = {}
    if body.filamentColors:
        for fc in body.filamentColors:
            color_hex_map[fc.label] = fc.hex
    else:
        for label in colors.get_labels():
            color_hex_map[label] = colors[label].hex

    threemf_content = await run_in_threadpool(
        generate_svg_3mf,
        vector_results=vector_results,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=colors,
        color_hex_map=color_hex_map,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
        detail_size=body.detailSize,
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
    filament_colors_dicts = [
        {
            "name": color.name,
            "hex": color.hex,
            "transmission_distance": color.td,
        }
        for color in body.resolved_colors.colors.values()
    ]
    preset_name = (
        body.filamentPreset.value if body.filamentPreset else
        None if body.filamentColors else DEFAULT_FILAMENT_PRESET
    )

    image_dimensions = body.imageDimensions.model_dump()

    settings_json = generate_print_settings(
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        filament_colors=filament_colors_dicts,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
        filament_preset=preset_name,
    )

    logger.info("Generated print settings JSON")

    return Response(
        content=settings_json,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=print_settings.json"}
    )
