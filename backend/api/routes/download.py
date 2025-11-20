"""
File download endpoints (CSV and STL)
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import logging

from api.models import DownloadCSVRequest, DownloadSTLRequest
from services.csv_generator import generate_csv
from services.stl_generator import generate_stl_zip

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
        # Convert Pydantic models to dicts
        color_blocks = [block.dict() for block in request.colorBlocks]

        # Generate CSV
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
    Generate and download ZIP file containing color-separated STL files

    Args:
        request: DownloadSTLRequest with colorBlocks and parameters

    Returns:
        ZIP file containing STL files
    """
    try:
        # Convert Pydantic models to dicts
        color_blocks = [block.dict() for block in request.colorBlocks]
        image_dimensions = request.imageDimensions.dict()

        # Generate STL ZIP
        zip_content = generate_stl_zip(
            color_blocks=color_blocks,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions
        )

        logger.info(f"Generated STL ZIP for {len(color_blocks)} colors, "
                   f"{image_dimensions['width']}x{image_dimensions['height']} pixels")

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
