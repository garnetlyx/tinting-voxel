"""
Image processing endpoints
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import logging
from typing import Optional
from io import BytesIO

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from PIL import Image

from api.error_handlers import handle_api_errors
from api.filament_payload import (
    get_colors_from_request,
    parse_filament_form_payload,
    resolve_layer_height,
)
from api.models import (
    ProcessImageResponse,
    ProcessingMode,
    SimulatePreviewRequest,
    SimulatedPrintPreviewResponse,
    SVGProcessImageResponse,
)
from api.rate_limiter import limiter
from api.validators import validate_image_upload
from services.image_processor import (
    MAX_PROCESSING_DIMENSION,
    _downscale_if_needed,
    _image_to_data_url,
    build_simulated_print_preview,
    build_vector_simulated_preview,
    process_image,
)
from services.vector_processor import (
    VectorProcessorConfig,
    process_image_vector_with_preview,
    render_vector_results_image,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Processing"])


@router.post("/process-image")
@limiter.limit("10/minute")
@handle_api_errors("processing image")
async def api_process_image(
    request: Request,
    image: UploadFile = File(...),
    mode: str = Form("pixel"),
    maxColors: int = Form(10, ge=1, le=1024),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.2, gt=0, le=10),
    epsilon: float = Form(2.0, gt=0, le=100),
    minArea: float = Form(4.0, gt=0, le=100),
    numColors: int = Form(8, ge=1, le=256),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.9),
    layerHeight: Optional[float] = Form(None, gt=0, le=10),
    layerCount: int = Form(4, ge=1, le=10),
    whiteBackingLayers: int = Form(DEFAULT_BACKING_LAYERS, ge=0, le=5),
    backingMode: str = Form("white", pattern=r'^(white|black)$'),
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

    # pixelSize remains the actual model scale. detailSize only controls
    # local feature merging in pixel mode; it does not force global upscaling.
    parsed_preset, parsed_colors = parse_filament_form_payload(
        filament_preset=filamentPreset,
        filament_colors=filamentColors,
    )
    colors = get_colors_from_request(parsed_preset, parsed_colors)
    layerHeight = resolve_layer_height(layerHeight, colors)

    if processing_mode == ProcessingMode.PIXEL:
        result = process_image(
            image_bytes=image_bytes,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize,
            filament_colors=colors,
            layer_count=layerCount,
            layer_height=layerHeight,
            white_backing_layers=whiteBackingLayers,
            backing_mode=backingMode,
            detail_size=detailSize,
        )

        logger.info(
            "Pixel mode - maxColors=%d, colorThreshold=%.1f, pixelSize=%.2f, detailSize=%s",
            maxColors, colorThreshold, pixelSize, str(detailSize)
        )
        logger.info(
            "Processed image: %dx%d, extracted %d colors",
            result['imageDimensions']['width'],
            result['imageDimensions']['height'],
            len(result['colorBlocks'])
        )

        return ProcessImageResponse(
            **result,
            pixelSize=pixelSize,
            detailSize=detailSize,
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

    # Standard safety downscale only; detailSize no longer drives global SVG resampling.
    img = _downscale_if_needed(img, MAX_PROCESSING_DIMENSION)
    img_array = np.array(img)

    config = VectorProcessorConfig(
        epsilon=epsilon,
        min_area=max(1, int(minArea / (pixelSize * pixelSize))),  # convert mm² → px²
        num_colors=numColors,
        pixel_size=pixelSize,
        detail_size=detailSize,
    )

    vector_results, quantized = process_image_vector_with_preview(img_array, config)

    from services.stl_generator import compute_reference_matrices
    from core.color_materials import Color

    # compute_reference_matrices serves every caller through the
    # content-keyed matrix cache.
    ref_code_matrix, ref_rgb_matrix = compute_reference_matrices(
        layerCount,
        layerHeight,
        colors,
        n_targets=len(vector_results),
        backing_layers=whiteBackingLayers,
        backing_mode=backingMode,
    )

    # Render segmentation image: show quantized colors (BEFORE mapping) with vector outlines
    # This shows the original quantized colors, not the printable blend colors
    segmentation_img = quantized.copy()
    
    # Render vector regions on top with outlines
    from services.vector_processor import normalize_regions, render_region_mask
    for idx, result in enumerate(vector_results):
        regions = normalize_regions(result)
        region_mask = render_region_mask(
            regions,
            width=img.width,
            height=img.height,
        )
        if region_mask.any():
            # Use original quantized color (not mapped)
            fill_color = tuple(result['color'])
            segmentation_img[region_mask] = fill_color
            
            # Draw outlines
            for region in regions:
                outer = region.get('outer', [])
                if len(outer) >= 3:
                    outer_pts = np.round(np.array(outer, dtype=np.float32)).astype(np.int32)
                    cv2.polylines(segmentation_img, [outer_pts], isClosed=True, color=(0, 0, 0), thickness=1)

    segmentation_image_data_url = _image_to_data_url(Image.fromarray(segmentation_img))

    logger.info(
        "SVG mode - epsilon=%.1f, minArea=%d, numColors=%d",
        epsilon, minArea, numColors
    )
    logger.info(
        "Processed image: %dx%d, extracted %d color groups",
        img.width, img.height, len(vector_results)
    )

    # Pass pre-computed reference matrices to avoid recomputation
    simulated_preview = build_vector_simulated_preview(
        quantized_image=quantized,
        vector_results=vector_results,
        pixel_size=pixelSize,
        detail_size=detailSize,
        colors=colors,
        layer_count=layerCount,
        layer_height=layerHeight,
        white_backing_layers=whiteBackingLayers,
        backing_mode=backingMode,
        ref_matrices=(ref_code_matrix, ref_rgb_matrix),  # Pass pre-computed matrices
    )

    return SVGProcessImageResponse(
        vectorResults=vector_results,
        processedImage=simulated_preview["processedImage"],
        segmentationImage=segmentation_image_data_url,
        mappedBlendPalette=simulated_preview["mappedBlendPalette"],
        imageDimensions={'width': img.width, 'height': img.height},
        pixelSize=pixelSize,
        detailSize=detailSize,
        printStack=simulated_preview["printStack"],
    )


@router.post("/simulate-preview", response_model=SimulatedPrintPreviewResponse)
@limiter.limit("20/minute")
@handle_api_errors("simulating print preview")
async def api_simulate_preview(request: Request, body: SimulatePreviewRequest):
    """Generate an image-specific simulated print preview from current color blocks."""
    colors = body.resolved_colors
    result = build_simulated_print_preview(
        color_blocks=[block.model_dump() for block in body.colorBlocks],
        image_dimensions=body.imageDimensions.model_dump(),
        colors=colors,
        layer_count=body.layerCount,
        layer_height=body.layerHeight,
        white_backing_layers=body.whiteBackingLayers,
        backing_mode=body.backingMode,
    )
    return SimulatedPrintPreviewResponse(**result)
