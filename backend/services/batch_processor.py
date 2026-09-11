"""
Batch image processing service.

Processes multiple images sequentially and returns per-image results.
"""
import logging
from io import BytesIO
from typing import Optional
from zipfile import ZipFile

from api.validators import validate_image_upload
from core.blend_color import Colors
from services.image_processor import process_image
from services.stl_generator import generate_stl_zip

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 20


def process_batch_images(
    files: list[tuple[str, bytes]],
    max_colors: int = 10,
    color_threshold: float = 50,
    pixel_size: float = 0.08,
    detail_size: Optional[float] = None,
) -> dict:
    """
    Process multiple images and return per-image color block results.

    Args:
        files: List of (filename, file_bytes) tuples
        max_colors: Maximum colors to extract per image
        color_threshold: Threshold for merging similar colors
        pixel_size: Physical size per pixel in mm

    Returns:
        Dictionary with results list, totalImages, successCount, errorCount

    Raises:
        ValueError: If batch is empty or exceeds MAX_BATCH_SIZE
    """
    if not files:
        raise ValueError("No images provided")
    if len(files) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch size {len(files)} exceeds maximum of {MAX_BATCH_SIZE}")

    results = []
    success_count = 0
    error_count = 0

    for filename, file_bytes in files:
        try:
            validate_image_upload(filename, file_bytes)
            result = process_image(
                image_bytes=file_bytes,
                max_colors=max_colors,
                color_threshold=color_threshold,
                pixel_size=pixel_size,
                detail_size=detail_size,
            )
            results.append({
                'filename': filename,
                'status': 'success',
                'colorBlocks': result['colorBlocks'],
                'processedImage': result['processedImage'],
                'imageDimensions': result['imageDimensions'],
            })
            success_count += 1
            logger.info("Batch: processed '%s' successfully", filename)
        except Exception as e:
            results.append({
                'filename': filename,
                'status': 'error',
                'error': str(e),
            })
            error_count += 1
            logger.warning("Batch: failed to process '%s': %s", filename, str(e))

    return {
        'results': results,
        'totalImages': len(files),
        'successCount': success_count,
        'errorCount': error_count,
    }


def generate_batch_stl_zip(
    batch_results: list[dict],
    layer_height: float,
    pixel_size: float,
    layer_count: int,
    colors: Optional[Colors] = None,
    white_backing_layers: int = 1,
    double_sided: bool = False,
) -> bytes:
    """
    Generate a ZIP containing per-image STL ZIPs from batch results.

    Args:
        batch_results: List of successful batch result dicts (with colorBlocks, imageDimensions)
        layer_height: Layer height in mm
        pixel_size: Pixel size in mm
        layer_count: Number of layers
        colors: Colors instance for color mapping
        double_sided: Whether to generate double-sided output

    Returns:
        ZIP file bytes containing per-image STL ZIP files

    Raises:
        ValueError: If no successful results provided
    """
    successful = [r for r in batch_results if r.get('status') == 'success']
    if not successful:
        raise ValueError("No successful image results to generate STL files from")

    if colors is None:
        colors = Colors()

    stl_success_count = 0
    stl_failure_count = 0

    outer_zip_buffer = BytesIO()
    with ZipFile(outer_zip_buffer, 'w') as outer_zip:
        for result in successful:
            filename = result['filename']
            # Strip extension for folder name
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename

            try:
                inner_zip_bytes = generate_stl_zip(
                    color_blocks=result['colorBlocks'],
                    layer_height=layer_height,
                    pixel_size=pixel_size,
                    layer_count=layer_count,
                    image_dimensions=result['imageDimensions'],
                    colors=colors,
                    white_backing_layers=white_backing_layers,
                    double_sided=double_sided,
                )
                outer_zip.writestr(f"{base_name}.zip", inner_zip_bytes)
                stl_success_count += 1
                logger.info("Batch STL: generated ZIP for '%s'", filename)
            except Exception as e:
                stl_failure_count += 1
                logger.warning(
                    "Batch STL: failed to generate STL for '%s': %s",
                    filename, str(e)
                )

        # If all STL generations failed, raise an error
        # This check must be inside the with block to avoid returning empty ZIP
        if stl_success_count == 0:
            raise ValueError(
                f"Failed to generate STL files for all {stl_failure_count} successful images"
            )

    logger.info(
        "Batch STL generation complete: %d succeeded, %d failed",
        stl_success_count, stl_failure_count
    )

    return outer_zip_buffer.getvalue()
