"""
Batch processing endpoints for multiple images.
"""
from config.print_defaults import DEFAULT_BACKING_LAYERS
import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from api.error_handlers import handle_api_errors
from api.filament_payload import get_colors_from_request, parse_filament_form_payload, resolve_layer_height
from api.models import BatchProcessResponse
from api.rate_limiter import limiter
from api.responses import json_response
from services.batch_processor import (
    MAX_BATCH_SIZE,
    generate_batch_stl_zip,
    process_batch_images,
)

logger = logging.getLogger(__name__)

# Maximum total batch size (50MB) to prevent memory exhaustion
MAX_TOTAL_BATCH_SIZE = 50 * 1024 * 1024

router = APIRouter(prefix="/api/batch", tags=["Batch Processing"])


def _validate_batch_input(images: List[UploadFile]):
    """Validate batch image count."""
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")
    if len(images) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Too many images ({len(images)}). Maximum batch size is {MAX_BATCH_SIZE}."
        )


async def _read_batch_files(images: List[UploadFile]) -> list:
    """Read uploaded files and validate total size."""
    files = []
    total_size = 0
    for img in images:
        file_bytes = await img.read()
        total_size += len(file_bytes)
        files.append((img.filename or 'unknown.png', file_bytes))

    if total_size > MAX_TOTAL_BATCH_SIZE:
        total_mb = total_size / (1024 * 1024)
        max_mb = MAX_TOTAL_BATCH_SIZE / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"Total batch size {total_mb:.1f}MB exceeds maximum {max_mb}MB"
        )
    return files


@router.post("/process", response_model=BatchProcessResponse)
@limiter.limit("3/minute")
@handle_api_errors("batch processing")
async def api_batch_process(
    request: Request,
    images: List[UploadFile] = File(...),
    maxColors: int = Form(10, ge=1, le=1024),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.2, gt=0, le=10),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.9),
):
    """Process multiple images in a single request (up to 20)."""
    _validate_batch_input(images)
    files = await _read_batch_files(images)

    # Use pixel_size directly - detail_size is now handled by pixel merging
    result = await run_in_threadpool(
        process_batch_images,
        files=files,
        max_colors=maxColors,
        color_threshold=colorThreshold,
        pixel_size=pixelSize,
        detail_size=detailSize,
    )

    logger.info(
        "Batch processed %d images: %d success, %d errors",
        result['totalImages'], result['successCount'], result['errorCount'],
    )

    return await run_in_threadpool(lambda: json_response(BatchProcessResponse(**result)))


@router.post("/download-stl")
@limiter.limit("2/minute")
@handle_api_errors("batch STL download")
async def api_batch_download_stl(
    request: Request,
    images: List[UploadFile] = File(...),
    maxColors: int = Form(10, ge=1, le=1024),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.2, gt=0, le=10),
    layerHeight: Optional[float] = Form(None, gt=0, le=10),
    layerCount: int = Form(4, ge=1, le=10),
    whiteBackingLayers: int = Form(DEFAULT_BACKING_LAYERS, ge=0, le=5),
    backingMode: str = Form("white", pattern=r'^(white|black)$'),
    filamentPreset: Optional[str] = Form(None),
    filamentColors: Optional[str] = Form(None),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.9),
):
    """Process multiple images and download all STL files as a single ZIP."""
    _validate_batch_input(images)
    files = await _read_batch_files(images)

    batch_result = await run_in_threadpool(
        process_batch_images,
        files=files,
        max_colors=maxColors,
        color_threshold=colorThreshold,
        pixel_size=pixelSize,
        detail_size=detailSize,
    )

    if batch_result['successCount'] == 0:
        raise HTTPException(status_code=422, detail="All images failed to process")

    # Resolve colors: filamentColors > filamentPreset > default (Bambu CMYWK)
    parsed_preset, parsed_colors = parse_filament_form_payload(filamentPreset, filamentColors)
    colors = get_colors_from_request(parsed_preset, parsed_colors)
    layerHeight = resolve_layer_height(layerHeight, colors)

    zip_content = await run_in_threadpool(
        generate_batch_stl_zip,
        batch_results=batch_result['results'],
        layer_height=layerHeight,
        pixel_size=pixelSize,
        layer_count=layerCount,
        colors=colors,
        white_backing_layers=whiteBackingLayers,
        backing_mode=backingMode,
    )

    logger.info(
        "Generated batch STL ZIP for %d/%d images",
        batch_result['successCount'], batch_result['totalImages'],
    )

    return Response(
        content=zip_content,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=batch_stl_output.zip"}
    )
