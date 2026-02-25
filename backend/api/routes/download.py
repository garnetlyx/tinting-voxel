"""
File download endpoints (CSV and STL)

V1 STL endpoints are superseded by V2 (/api/v2/download-stl, /api/v2/download-svg-stl).
These endpoints remain for backward compatibility.
"""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from api.error_handlers import handle_api_errors
from api.rate_limiter import limiter
from api.models import (
    DownloadCSVRequest,
    DownloadSTLRequest,
    DownloadSVGSTLRequest,
)
from core.blend_color import Colors
from services.csv_generator import generate_csv
from services.stl_generator import generate_stl_zip
from services.svg_stl_generator import generate_svg_stl_zip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Downloads"])

V1_STL_DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Link": '</api/v2/download-stl>; rel="successor-version"',
}

V1_SVG_STL_DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Link": '</api/v2/download-svg-stl>; rel="successor-version"',
}


@router.post("/download-csv")
@limiter.limit("20/minute")
@handle_api_errors("generating CSV")
async def api_download_csv(request: Request, body: DownloadCSVRequest):
    """Generate and download CSV file with color data."""
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    csv_content = generate_csv(color_blocks)

    logger.info("Generated CSV for %d colors", len(color_blocks))

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=colors.csv"}
    )


@router.post("/download-stl", deprecated=True)
@limiter.limit("5/minute")
@handle_api_errors("generating STL")
async def api_download_stl(request: Request, body: DownloadSTLRequest):
    """Deprecated: use /api/v2/download-stl."""
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    image_dimensions = body.imageDimensions.model_dump()

    # V1 always uses default CMYK colors
    zip_content = generate_stl_zip(
        color_blocks=color_blocks,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=Colors()
    )

    logger.info(
        "Generated STL ZIP (pixel mode) for %d colors, %dx%d pixels",
        len(color_blocks), image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=all_color_blocks.zip",
            **V1_STL_DEPRECATION_HEADERS,
        }
    )


@router.post("/download-svg-stl", deprecated=True)
@limiter.limit("5/minute")
@handle_api_errors("generating SVG STL")
async def api_download_svg_stl(request: Request, body: DownloadSVGSTLRequest):
    """Deprecated: use /api/v2/download-svg-stl."""
    vector_results = [result.model_dump() for result in body.vectorResults]
    image_dimensions = body.imageDimensions.model_dump()

    # V1 always uses default CMYK colors
    zip_content = generate_svg_stl_zip(
        vector_results=vector_results,
        layer_height=body.layerHeight,
        pixel_size=body.pixelSize,
        layer_count=body.layerCount,
        image_dimensions=image_dimensions,
        colors=Colors()
    )

    logger.info(
        "Generated STL ZIP (SVG mode) for %d color groups, %dx%d pixels",
        len(vector_results), image_dimensions['width'], image_dimensions['height']
    )

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=all_color_blocks.zip",
            **V1_SVG_STL_DEPRECATION_HEADERS,
        }
    )
