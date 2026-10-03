"""
Filament preview endpoint for color configuration analysis.

Generates a visual preview of achievable colors from a filament configuration.
"""
import logging

from fastapi import APIRouter, Request, Response

from api.budget_guard import check_memory_budget
from api.concurrency import run_heavy
from api.error_handlers import handle_api_errors
from api.models import FilamentPreviewRequest, FilamentPreviewResponse
from api.rate_limiter import limiter
from api.responses import json_response
from config.settings import settings
from services import memory_estimate
from services.filament_preview import FilamentPreviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Filament"])


@router.post("/filament-preview", response_model=FilamentPreviewResponse)
@limiter.limit("10/minute")
@handle_api_errors("generating filament preview")
async def api_filament_preview(request: Request, body: FilamentPreviewRequest):
    """Generate a color matrix preview for the given filament configuration."""
    colors = body.resolved_colors
    n_labels = len(colors.get_labels())
    check_memory_budget(
        "filament_preview",
        memory_estimate.filament_preview_mb(n_labels, body.layerCount, body.pageSize),
        memory_estimate.suggest_filament_preview(
            n_labels, body.layerCount, body.pageSize, settings.heavy_memory_budget_mb,
        ),
        body.forceOversize,
    )
    service = FilamentPreviewService(
        colors,
        layer_count=body.layerCount,
        layer_height=body.layerHeight,
        backing_layers=body.whiteBackingLayers,
        backing_filament=body.backingFilament,
    )

    def build_preview_response() -> Response:
        result = service.generate_preview(page=body.page, page_size=body.pageSize)
        warnings = service.check_similar_colors()

        logger.info(
            "Generated filament preview: %d colors, %d combinations",
            result["stats"]["colorCount"], result["stats"]["combinationCount"]
        )

        return json_response(FilamentPreviewResponse(
            image=result["image"],
            colorMatrix=result["colorMatrix"],
            stats=result["stats"],
            imageDimensions=result["imageDimensions"],
            warnings=warnings,
            pagination=result.get("pagination"),
        ))

    return await run_heavy("filament_preview", build_preview_response)
