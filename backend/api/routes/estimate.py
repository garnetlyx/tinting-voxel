"""Pre-flight memory estimates for heavy jobs.

The browser calls this before submitting a heavy request; when the estimate
is over the server's memory budget the answer carries the same scale-down
suggestion the confirmation dialog offers.
"""
import logging
import math

from fastapi import APIRouter, HTTPException, Request

from api.error_handlers import handle_api_errors
from api.models import EstimateJobRequest
from api.rate_limiter import limiter
from config.print_defaults import DEFAULT_BACKING_LAYERS
from config.settings import settings
from core.stack_prune import is_translucent_set
from services import memory_estimate
from services.telemetry import emit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["Estimate"])


@router.post("/estimate-job")
@limiter.limit("60/minute")
@handle_api_errors("estimating job memory")
async def api_estimate_job(request: Request, body: EstimateJobRequest):
    """Estimate a heavy job's peak memory and how to fit it in the budget."""
    budget = settings.heavy_memory_budget_mb

    if body.kind == "filament_preview":
        params = body.filamentPreview
        if params is None:
            _malformed("filamentPreview")
        colors = params.resolved_colors
        n_labels = len(colors.get_labels())
        estimate = memory_estimate.filament_preview_mb(n_labels, params.layerCount, params.pageSize)
        suggestion = memory_estimate.suggest_filament_preview(
            n_labels, params.layerCount, params.pageSize, budget,
        )

    elif body.kind == "process_image":
        params = body.processImage
        if params is None:
            _malformed("processImage")
        colors = params.resolved_colors
        n_labels = len(colors.get_labels())
        translucent = is_translucent_set(colors)
        cells = memory_estimate.grid_cells(params.imageWidth, params.imageHeight, params.pixelSize, params.detailSize)
        targets = params.maxColors if params.mode.value == "pixel" else params.numColors
        estimate = memory_estimate.process_image_mb(
            params.mode.value, cells, n_labels, params.layerCount, targets, translucent,
        )
        suggestion = memory_estimate.suggest_process_image(
            params.mode.value, cells, params.pixelSize, n_labels, params.layerCount,
            targets, translucent, budget,
        )

    elif body.kind == "download":
        params = body.download
        if params is None:
            _malformed("download")
        colors = params.resolved_colors
        n_labels = len(colors.get_labels())
        translucent = is_translucent_set(colors)
        estimate = memory_estimate.download_mb(
            params.cells, params.layerCount, n_labels, translucent, DEFAULT_BACKING_LAYERS,
        )
        suggestion = memory_estimate.suggest_download(
            params.cells, n_labels, params.layerCount, translucent, budget,
        )

    else:  # batch
        params = body.batch
        if params is None:
            _malformed("batch")
        cells = memory_estimate.grid_cells(params.imageWidth, params.imageHeight, params.pixelSize, params.detailSize)
        estimate = memory_estimate.batch_mb(params.images, cells)
        # A batch's grids keep each upload's own resolution, so no request-side
        # parameter reduces it; the dialog offers run-anyway or cancel.
        suggestion = None

    emit(
        "memory_estimate", kind=body.kind, estimated_mb=round(estimate),
        budget_mb=round(budget), verdict="ok" if estimate <= budget else "oversize",
        endpoint="estimate",
    )
    return memory_estimate.Estimate(
        kind=body.kind, estimated_mb=estimate, budget_mb=budget,
        within_budget=estimate <= budget, suggestion=suggestion,
    ).as_dict()


def _malformed(field: str) -> None:
    raise HTTPException(status_code=422, detail=f"kind requires a '{field}' params object.")
