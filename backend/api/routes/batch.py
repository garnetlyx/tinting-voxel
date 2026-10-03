"""
Batch processing endpoints for multiple images.
"""
from config.settings import settings
from config.print_defaults import DEFAULT_BACKING_LAYERS, MAX_COLOR_LAYERS
import logging
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from PIL import Image

from api.budget_guard import check_memory_budget
from api.concurrency import run_heavy
from api.error_handlers import handle_api_errors
from api.filament_payload import get_colors_from_request, parse_filament_form_payload, resolve_layer_height
from api.models import BatchProcessResponse
from api.rate_limiter import limiter
from api.responses import json_response
from core.stack_prune import is_translucent_set
from services import memory_estimate
from services.telemetry import emit
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


def _max_grid_cells(files: list, pixel_size: float, detail_size: Optional[float]) -> int:
    """Largest model grid among the batch's images (headers only, no decode).

    Unreadable files are skipped: the batch job itself reports them per image.
    """
    largest = 0
    for _, file_bytes in files:
        try:
            with Image.open(BytesIO(file_bytes)) as header:
                cells = memory_estimate.grid_cells(header.width, header.height, pixel_size, detail_size)
        except Exception:
            continue
        largest = max(largest, cells)
    return largest


@router.post("/process", response_model=BatchProcessResponse)
@limiter.limit("3/minute")
@handle_api_errors("batch processing")
async def api_batch_process(
    request: Request,
    images: List[UploadFile] = File(...),
    maxColors: int = Form(10, ge=1, le=settings.max_target_colors),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.2, gt=0, le=10),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.9),
    forceOversize: bool = Form(False),
):
    """Process multiple images in a single request (up to 20)."""
    _validate_batch_input(images)
    files = await _read_batch_files(images)
    check_memory_budget(
        "batch_process",
        memory_estimate.batch_mb(len(files), _max_grid_cells(files, pixelSize, detailSize)),
        None,
        forceOversize,
    )

    def build_batch_response() -> Response:
        # Use pixel_size directly - detail_size is now handled by pixel merging
        result = process_batch_images(
            files=files,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize,
            detail_size=detailSize,
        )
        emit("batch_processed", images=result['totalImages'], succeeded=result['successCount'],
             failed=result['errorCount'])
        logger.info(
            "Batch processed %d images: %d success, %d errors",
            result['totalImages'], result['successCount'], result['errorCount'],
        )
        return json_response(BatchProcessResponse(**result))

    return await run_heavy("batch_process", build_batch_response)


@router.post("/download-stl")
@limiter.limit("2/minute")
@handle_api_errors("batch STL download")
async def api_batch_download_stl(
    request: Request,
    images: List[UploadFile] = File(...),
    maxColors: int = Form(10, ge=1, le=settings.max_target_colors),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.2, gt=0, le=10),
    layerHeight: Optional[float] = Form(None, gt=0, le=10),
    layerCount: int = Form(4, ge=1, le=MAX_COLOR_LAYERS),
    whiteBackingLayers: int = Form(DEFAULT_BACKING_LAYERS, ge=0, le=5),
    backingFilament: Optional[str] = Form(None, pattern=r'^[A-Z]$'),
    filamentPreset: Optional[str] = Form(None),
    filamentColors: Optional[str] = Form(None),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.9),
    forceOversize: bool = Form(False),
):
    """Process multiple images and download all STL files as a single ZIP."""
    _validate_batch_input(images)
    files = await _read_batch_files(images)

    # Resolve colors: filamentColors > filamentPreset > default (Bambu CMYWK)
    parsed_preset, parsed_colors = parse_filament_form_payload(filamentPreset, filamentColors)
    colors = get_colors_from_request(parsed_preset, parsed_colors)
    layerHeight = resolve_layer_height(layerHeight, colors)
    translucent = is_translucent_set(colors)
    cells = _max_grid_cells(files, pixelSize, detailSize)
    check_memory_budget(
        "batch_download_stl",
        memory_estimate.batch_mb(len(files), cells)
        + memory_estimate.download_mb(cells, layerCount, len(colors.get_labels()), translucent, whiteBackingLayers),
        memory_estimate.suggest_download(
            cells, len(colors.get_labels()), layerCount, translucent, settings.heavy_memory_budget_mb,
        ),
        forceOversize,
    )

    def build_batch_zip() -> Response:
        batch_result = process_batch_images(
            files=files,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize,
            detail_size=detailSize,
        )

        if batch_result['successCount'] == 0:
            raise HTTPException(status_code=422, detail="All images failed to process")

        zip_content = generate_batch_stl_zip(
            batch_results=batch_result['results'],
            layer_height=layerHeight,
            layer_count=layerCount,
            colors=colors,
            white_backing_layers=whiteBackingLayers,
            backing_filament=backingFilament,
        )

        emit("model_exported", format="batch-stl", groups=batch_result['successCount'], bytes=len(zip_content))
        logger.info(
            "Generated batch STL ZIP for %d/%d images",
            batch_result['successCount'], batch_result['totalImages'],
        )
        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=batch_stl_output.zip"},
        )

    return await run_heavy("batch_download_stl", build_batch_zip)
