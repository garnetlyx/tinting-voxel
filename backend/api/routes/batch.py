"""
Batch processing endpoints for multiple images.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from api.error_handlers import handle_api_errors
from api.models import BatchProcessResponse, FilamentPreset
from api.rate_limiter import limiter
from core.blend_color import Colors
from core.color_config import ColorConfig, get_preset
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
    maxColors: int = Form(10, ge=1, le=256),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.08, gt=0, le=10),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.8),
):
    """Process multiple images in a single request (up to 20)."""
    _validate_batch_input(images)
    files = await _read_batch_files(images)

    # Use pixel_size directly - detail_size is now handled by pixel merging
    result = process_batch_images(
        files=files,
        max_colors=maxColors,
        color_threshold=colorThreshold,
        pixel_size=pixelSize,
    )

    logger.info(
        "Batch processed %d images: %d success, %d errors",
        result['totalImages'], result['successCount'], result['errorCount'],
    )

    return BatchProcessResponse(**result)


@router.post("/download-stl")
@limiter.limit("2/minute")
@handle_api_errors("batch STL download")
async def api_batch_download_stl(
    request: Request,
    images: List[UploadFile] = File(...),
    maxColors: int = Form(10, ge=1, le=256),
    colorThreshold: float = Form(50, ge=0, le=1000),
    pixelSize: float = Form(0.08, gt=0, le=10),
    layerHeight: float = Form(0.08, gt=0, le=10),
    layerCount: int = Form(4, ge=1, le=10),
    basePlateThickness: float = Form(0.0, ge=0, le=10),
    doubleSided: bool = Form(False),
    filamentPreset: Optional[str] = Form(None),
    filamentColors: Optional[str] = Form(None),
    detailSize: Optional[float] = Form(None, ge=0.2, le=0.8),
):
    """Process multiple images and download all STL files as a single ZIP."""
    if detailSize is not None and pixelSize < detailSize:
        raise HTTPException(
            status_code=422,
            detail=f"pixelSize ({pixelSize}) cannot be smaller than detailSize ({detailSize})"
        )

    _validate_batch_input(images)
    files = await _read_batch_files(images)

    batch_result = process_batch_images(
        files=files,
        max_colors=maxColors,
        color_threshold=colorThreshold,
        pixel_size=pixelSize,
    )

    if batch_result['successCount'] == 0:
        raise HTTPException(status_code=422, detail="All images failed to process")

    # Resolve colors: filamentColors > filamentPreset > default (Phase 6 CMYK with Key/black)
    default_configs = get_preset(FilamentPreset.BAMBU_CMYK_PHASE6.value)
    colors = Colors.from_configs(default_configs) if default_configs else Colors()
    if filamentColors:
        try:
            import json
            colors_data = json.loads(filamentColors)
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filamentColors JSON: {str(e)}"
            )
        try:
            configs = [
                ColorConfig(
                    name=fc['name'],
                    hex=fc['hex'],
                    transmission_distance=fc['transmission_distance'],
                    alpha=fc.get('alpha', 12.0),
                    k=fc.get('k', 10.0),
                    td_scale=fc.get('td_scale', 1.0),
                    td_gamma=fc.get('td_gamma', 1.0),
                )
                for fc in colors_data
            ]
            colors = Colors.from_configs(configs)
        except (KeyError, TypeError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filamentColors format: {str(e)}"
            )
    elif filamentPreset:
        try:
            preset_enum = FilamentPreset(filamentPreset)
            preset_configs = get_preset(preset_enum.value)
            if preset_configs:
                colors = Colors.from_configs(preset_configs)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filament preset: {filamentPreset}. "
                f"Valid presets: bambu_cmyk, bambu_cmyk_calibrated, bambu_cmyk_phase6, bambu_cmyw_phase6, clear_cmyk"
            )

    zip_content = generate_batch_stl_zip(
        batch_results=batch_result['results'],
        layer_height=layerHeight,
        pixel_size=pixelSize,
        layer_count=layerCount,
        colors=colors,
        base_plate_thickness=basePlateThickness,
        double_sided=doubleSided,
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
