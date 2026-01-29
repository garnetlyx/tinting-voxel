"""
V2 Download endpoints with configurable filament colors.

Maintains backward compatibility while adding N-color support.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.models import (
    DownloadSTLRequestV2,
    DownloadSVGSTLRequestV2,
    FilamentColorConfig,
    FilamentPreset,
    FilamentPresetInfo,
    FilamentPresetsResponse,
)
from core.blend_color import Colors
from core.color_config import (
    BAMBU_CMYK_PRESET,
    CLEAR_CMYK_PRESET,
    ColorConfig,
    get_preset,
)
from services.stl_generator import generate_stl_zip, initialize_color_mapping
from services.svg_stl_generator import generate_svg_stl_zip

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
                transmission_distance=fc.transmission_distance
            )
            for fc in filament_colors
        ]
        return Colors.from_configs(configs)

    if filament_preset:
        # Use preset
        preset_configs = get_preset(filament_preset.value)
        if preset_configs:
            return Colors.from_configs(preset_configs)

    # Fall back to default CMYK
    return Colors()


@router.get("/filament-presets", response_model=FilamentPresetsResponse)
async def api_get_filament_presets():
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
                    transmission_distance=c.transmission_distance
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
                    transmission_distance=c.transmission_distance
                )
                for c in CLEAR_CMYK_PRESET
            ]
        ),
    ]
    return FilamentPresetsResponse(presets=presets)


@router.post("/download-stl")
async def api_download_stl_v2(request: DownloadSTLRequestV2):
    """
    Generate and download ZIP file containing color-separated STL files.

    Supports configurable filament colors (4-10 colors).

    Args:
        request: DownloadSTLRequestV2 with colorBlocks, parameters, and optional colors

    Returns:
        ZIP file containing STL files
    """
    try:
        # Get colors configuration
        colors = get_colors_from_request(
            request.filamentPreset,
            request.filamentColors
        )

        # Re-initialize color mapping with new colors
        initialize_color_mapping(
            layer_count=request.layerCount,
            layer_height=request.layerHeight,
            colors=colors
        )

        color_blocks = [block.dict() for block in request.colorBlocks]
        image_dimensions = request.imageDimensions.dict()

        zip_content = generate_stl_zip(
            color_blocks=color_blocks,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions,
            colors=colors
        )

        color_count = len(colors)
        logger.info(
            "Generated STL ZIP (v2, %d colors) for %d color blocks, %dx%d pixels",
            color_count,
            len(color_blocks),
            image_dimensions['width'],
            image_dimensions['height']
        )

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=all_color_blocks.zip"
            }
        )

    except Exception as e:
        logger.error(f"Error generating STL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate STL: {str(e)}")


@router.post("/download-svg-stl")
async def api_download_svg_stl_v2(request: DownloadSVGSTLRequestV2):
    """
    Generate and download ZIP file containing color-separated STL files (SVG mode).

    Supports configurable filament colors (4-10 colors).

    Args:
        request: DownloadSVGSTLRequestV2 with vectorResults, parameters, and optional colors

    Returns:
        ZIP file containing STL files
    """
    try:
        # Get colors configuration
        colors = get_colors_from_request(
            request.filamentPreset,
            request.filamentColors
        )

        # Re-initialize color mapping with new colors
        initialize_color_mapping(
            layer_count=request.layerCount,
            layer_height=request.layerHeight,
            colors=colors
        )

        vector_results = [result.dict() for result in request.vectorResults]
        image_dimensions = request.imageDimensions.dict()

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions,
            colors=colors
        )

        color_count = len(colors)
        logger.info(
            "Generated STL ZIP (v2 SVG mode, %d colors) for %d color groups, %dx%d pixels",
            color_count,
            len(vector_results),
            image_dimensions['width'],
            image_dimensions['height']
        )

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=all_color_blocks.zip"
            }
        )

    except Exception as e:
        logger.error(f"Error generating SVG STL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate STL: {str(e)}")
