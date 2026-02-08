"""
Filament preview endpoint for color configuration analysis.

Generates a visual preview of achievable colors from a filament configuration.
"""
import logging

from fastapi import APIRouter, Request

from api.error_handlers import handle_api_errors
from api.models import FilamentPreviewRequest, FilamentPreviewResponse
from api.rate_limiter import limiter
from api.routes.download_v2 import get_colors_from_request
from services.filament_preview import FilamentPreviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Filament"])


@router.post("/filament-preview", response_model=FilamentPreviewResponse)
@limiter.limit("10/minute")
@handle_api_errors("generating filament preview")
async def api_filament_preview(request: Request, body: FilamentPreviewRequest):
    """Generate a color matrix preview for the given filament configuration."""
    colors = get_colors_from_request(body.filamentPreset, body.filamentColors)
    service = FilamentPreviewService(
        colors,
        layer_count=body.layerCount,
        layer_height=body.layerHeight,
    )

    result = service.generate_preview(page=body.page, page_size=body.pageSize)
    warnings = service.check_similar_colors()

    logger.info(
        "Generated filament preview: %d colors, %d combinations",
        result["stats"]["colorCount"], result["stats"]["combinationCount"]
    )

    return FilamentPreviewResponse(
        image=result["image"],
        colorMatrix=result["colorMatrix"],
        stats=result["stats"],
        imageDimensions=result["imageDimensions"],
        warnings=warnings,
        pagination=result.get("pagination"),
    )
