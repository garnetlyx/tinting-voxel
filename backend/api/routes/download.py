"""
File download endpoints (CSV and STL)
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from api.models import (
    DownloadCSVRequest,
    DownloadSTLRequest,
    DownloadSVGSTLRequest,
    ProcessingMode,
)
from services.csv_generator import generate_csv
from services.stl_generator import generate_stl_zip
from services.svg_stl_generator import generate_svg_stl_zip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Downloads"])


@router.post("/download-csv")
async def api_download_csv(request: DownloadCSVRequest):
    """
    Generate and download CSV file with color data

    Args:
        request: DownloadCSVRequest with colorBlocks

    Returns:
        CSV file as response
    """
    try:
        color_blocks = [block.dict() for block in request.colorBlocks]
        csv_content = generate_csv(color_blocks)

        logger.info(f"Generated CSV for {len(color_blocks)} colors")

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=colors.csv"
            }
        )

    except Exception as e:
        logger.error(f"Error generating CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {str(e)}")


@router.post("/download-stl")
async def api_download_stl(request: DownloadSTLRequest):
    """
    Generate and download ZIP file containing color-separated STL files (pixel mode).

    Args:
        request: DownloadSTLRequest with colorBlocks and parameters

    Returns:
        ZIP file containing STL files
    """
    try:
        color_blocks = [block.dict() for block in request.colorBlocks]
        image_dimensions = request.imageDimensions.dict()

        zip_content = generate_stl_zip(
            color_blocks=color_blocks,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions
        )

        logger.info(
            "Generated STL ZIP (pixel mode) for %d colors, %dx%d pixels",
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
async def api_download_svg_stl(request: DownloadSVGSTLRequest):
    """
    Generate and download ZIP file containing color-separated STL files (SVG mode).

    Args:
        request: DownloadSVGSTLRequest with vectorResults and parameters

    Returns:
        ZIP file containing STL files
    """
    try:
        vector_results = [result.dict() for result in request.vectorResults]
        image_dimensions = request.imageDimensions.dict()

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions
        )

        logger.info(
            "Generated STL ZIP (SVG mode) for %d color groups, %dx%d pixels",
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
