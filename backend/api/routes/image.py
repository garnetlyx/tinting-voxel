"""
Image processing endpoints
"""
import base64
import logging
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from api.models import ProcessImageResponse, ProcessingMode, SVGProcessImageResponse
from services.image_processor import process_image
from services.vector_processor import VectorProcessorConfig, process_image_vector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Processing"])


@router.post("/process-image")
async def api_process_image(
    image: UploadFile = File(...),
    mode: str = Form("pixel"),
    maxColors: int = Form(10),
    colorThreshold: float = Form(50),
    pixelSize: float = Form(0.08),
    epsilon: float = Form(2.0),
    minArea: int = Form(100),
    numColors: int = Form(8)
):
    """
    Process uploaded image to extract color blocks or vector contours.

    Args:
        image: Uploaded image file
        mode: Processing mode ('pixel' or 'svg')
        maxColors: Maximum number of colors to extract (pixel mode)
        colorThreshold: Threshold for merging similar colors (pixel mode)
        pixelSize: Physical size of each pixel in mm
        epsilon: Douglas-Peucker simplification tolerance (svg mode)
        minArea: Minimum contour area in pixels (svg mode)
        numColors: Number of colors to quantize to (svg mode)

    Returns:
        ProcessImageResponse (pixel mode) or SVGProcessImageResponse (svg mode)
    """
    try:
        image_bytes = await image.read()
        processing_mode = ProcessingMode(mode)

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

        else:  # SVG mode
            img = Image.open(BytesIO(image_bytes))
            img = img.convert('RGB')
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

            # Draw contour lines on the image
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

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
