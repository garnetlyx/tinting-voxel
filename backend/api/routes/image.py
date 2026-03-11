"""
Image processing endpoints
"""
import base64
import json
import logging
from typing import Optional
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from api.error_handlers import handle_api_errors
from api.models import (
    FilamentColorConfig,
    FilamentConfigMixin,
    FilamentPreset,
    ProcessImageResponse,
    ProcessingMode,
    SimulatePreviewRequest,
    SimulatedPrintPreviewResponse,
    SVGProcessImageResponse,
)
from api.rate_limiter import limiter
from api.routes.download_v2 import get_colors_from_request
from api.validators import validate_image_upload
from services.image_processor import (
    MAX_PROCESSING_DIMENSION,
    _downscale_if_needed,
    build_simulated_print_preview,
    process_image,
)
from services.vector_processor import VectorProcessorConfig, process_image_vector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Processing"])


def _parse_filament_form_payload(
    filament_preset: Optional[str],
    filament_colors: Optional[str],
) -> tuple[Optional[FilamentPreset], Optional[list[FilamentColorConfig]]]:
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
                    "Valid presets: bambu_cmyk, bambu_cmyk_calibrated, bambu_cmyk_phase6, bambu_cmyw_phase6, clear_cmyk"
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
    numColors: int = Form(8, ge=1, le=256),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.8),
    targetWidth: Optional[float] = Form(None, ge=1, le=500),
    layerHeight: float = Form(0.08, gt=0, le=10),
    layerCount: int = Form(4, ge=1, le=10),
    filamentPreset: Optional[str] = Form(None),
    filamentColors: Optional[str] = Form(None),
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

    # Clamp pixelSize upward to honour detailSize minimum if provided
    effective_pixel_size = pixelSize
    if detailSize is not None:
        effective_pixel_size = max(pixelSize, detailSize)

    parsed_preset, parsed_colors = _parse_filament_form_payload(
        filament_preset=filamentPreset,
        filament_colors=filamentColors,
    )
    colors = get_colors_from_request(parsed_preset, parsed_colors)

    if processing_mode == ProcessingMode.PIXEL:
        result = process_image(
            image_bytes=image_bytes,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=effective_pixel_size,
            filament_colors=colors,
            layer_count=layerCount,
            layer_height=layerHeight,
            target_width=targetWidth,
            detail_size=detailSize,
        )

        logger.info(
            "Pixel mode - maxColors=%d, colorThreshold=%.1f, pixelSize=%.2f, detailSize=%s, targetWidth=%s",
            maxColors, colorThreshold, pixelSize, str(detailSize), str(targetWidth)
        )
        logger.info(
            "Processed image: %dx%d, extracted %d colors",
            result['imageDimensions']['width'],
            result['imageDimensions']['height'],
            len(result['colorBlocks'])
        )

        return ProcessImageResponse(
            **result,
            pixelSize=effective_pixel_size,
            detailSize=detailSize
        )

    # SVG mode
    img = Image.open(BytesIO(image_bytes))
    # Convert RGBA to RGB with white background if needed
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    else:
        img = img.convert('RGB')

    # Explicit user-intended scaling if targetWidth is provided
    if targetWidth is not None and detailSize is not None and detailSize > 0:
        intended_pixels = int(targetWidth / detailSize)
        if intended_pixels > 0:
            w, h = img.size
            new_width = intended_pixels
            new_height = int(h * (intended_pixels / w))
            if new_width != w or new_height != h:
                logger.info(
                    "SVG mode: Scaling image to user-intended targetWidth (%.1fmm / %.2fmm): %dx%d (original %dx%d)",
                    targetWidth, detailSize, new_width, new_height, w, h
                )
                img = img.resize((new_width, new_height), Image.LANCZOS)
        # Apply safety downscale with higher cap for intentional sized prints
        img = _downscale_if_needed(img, 2048)
    else:
        # Standard safety downscale
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
        imageDimensions={'width': img.width, 'height': img.height},
        pixelSize=effective_pixel_size,
        detailSize=detailSize
    )


@router.post("/simulate-preview", response_model=SimulatedPrintPreviewResponse)
@limiter.limit("20/minute")
@handle_api_errors("simulating print preview")
async def api_simulate_preview(request: Request, body: SimulatePreviewRequest):
    """Generate an image-specific simulated print preview from current color blocks."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    result = build_simulated_print_preview(
        color_blocks=[block.model_dump() for block in body.colorBlocks],
        image_dimensions=body.imageDimensions.model_dump(),
        colors=colors,
        layer_count=body.layerCount,
        layer_height=body.layerHeight,
    )
    return SimulatedPrintPreviewResponse(**result)
