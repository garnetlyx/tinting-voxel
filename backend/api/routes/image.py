"""
Image processing endpoints
"""
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.models import ProcessImageResponse
from services.image_processor import process_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Processing"])


@router.post("/process-image", response_model=ProcessImageResponse)
async def api_process_image(
    image: UploadFile = File(...),
    maxColors: int = Form(10),
    colorThreshold: float = Form(50),
    pixelSize: float = Form(0.08)
):
    """
    Process uploaded image to extract color blocks

    Args:
        image: Uploaded image file
        maxColors: Maximum number of colors to extract
        colorThreshold: Threshold for merging similar colors
        pixelSize: Physical size of each pixel in mm

    Returns:
        ProcessImageResponse with colorBlocks, processedImage, and imageDimensions
    """
    try:
        # Read image bytes
        image_bytes = await image.read()

        # Process image
        result = process_image(
            image_bytes=image_bytes,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize
        )

        logger.info(f"Request parameters: maxColors={maxColors}, colorThreshold={colorThreshold}, pixelSize={pixelSize}")
        logger.info(f"Processed image: {result['imageDimensions']['width']}x{result['imageDimensions']['height']}, "
                   f"extracted {len(result['colorBlocks'])} colors")

        return result

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
