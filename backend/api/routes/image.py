"""
Image processing endpoints
"""
import base64
import logging
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from api.error_handlers import handle_api_errors
from api.models import ProcessImageResponse, ProcessingMode, SVGProcessImageResponse
from api.rate_limiter import limiter
from api.validators import validate_image_upload
from services.image_processor import process_image, _downscale_if_needed, MAX_PROCESSING_DIMENSION
from services.vector_processor import VectorProcessorConfig, process_image_vector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Processing"])


@router.post("/process-image")
@limiter.limit("10/minute")
@handle_api_errors("processing image")
async def api_process_image(
    request: Request,
    image: UploadFile = File(...),
    mode: str = Form("pixel"),
    maxColors: int = Form(10, ge=1, le=256),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.08, gt=0, le=10),
    epsilon: float = Form(2.0, gt=0, le=100),
    minArea: int = Form(100, ge=1),
    numColors: int = Form(8, ge=1, le=256)
):
    """Process uploaded image to extract color blocks or vector contours."""
    image_bytes = await image.read()
    validate_image_upload(image.filename, image_bytes)

    try:
        processing_mode = ProcessingMode(mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid processing mode: '{mode}'. Must be 'pixel' or 'svg'."
        )

    if processing_mode == ProcessingMode.PIXEL:
        result = process_image(
            image_bytes=image_bytes,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize
        )

        logger.info(
            "Pixel mode - maxColors=%d, colorThreshold=%.1f, pixelSize=%.2f",
            maxColors, colorThreshold, pixelSize
        )
        logger.info(
            "Processed image: %dx%d, extracted %d colors",
            result['imageDimensions']['width'],
            result['imageDimensions']['height'],
            len(result['colorBlocks'])
        )

        return ProcessImageResponse(**result)

    # SVG mode
    img = Image.open(BytesIO(image_bytes))
    # Convert RGBA to RGB with white background if needed
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    else:
        img = img.convert('RGB')
    # Downscale large images to prevent memory issues
    img = _downscale_if_needed(img, MAX_PROCESSING_DIMENSION)
    img_array = np.array(img)

    config = VectorProcessorConfig(
        epsilon=epsilon,
        min_area=minArea,
        num_colors=numColors
    )

    vector_results = process_image_vector(img_array, config)

    # Generate processed image preview (quantized colors with contour lines)
    import cv2
    from services.vector_processor import quantize_colors
    quantized, _ = quantize_colors(img_array, numColors)
    result_img = quantized.copy()

    for vr in vector_results:
        for polygon in vr['polygons']:
            pts = np.array(polygon, dtype=np.int32)
            cv2.polylines(result_img, [pts], isClosed=True, color=(0, 0, 0), thickness=1)

    processed_img = Image.fromarray(result_img)
    buffered = BytesIO()
    processed_img.save(buffered, format="PNG")
    processed_img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    processed_img_data_url = f"data:image/png;base64,{processed_img_base64}"

    logger.info(
        "SVG mode - epsilon=%.1f, minArea=%d, numColors=%d",
        epsilon, minArea, numColors
    )
    logger.info(
        "Processed image: %dx%d, extracted %d color groups",
        img.width, img.height, len(vector_results)
    )

    return SVGProcessImageResponse(
        vectorResults=vector_results,
        processedImage=processed_img_data_url,
        imageDimensions={'width': img.width, 'height': img.height}
    )
