"""
Parameter search API endpoints.

POST /api/param-search       — run parameter search, return top-N results
GET  /api/param-search/progress/{job_id} — SSE stream of ProgressEvent objects
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from api.error_handlers import handle_api_errors
from api.filament_payload import get_colors_from_request, parse_filament_form_payload
from api.models import (
    ParamSearchRequest,
    ParamSearchResponse,
    ProgressEvent,
    SearchResultItem,
)
from api.rate_limiter import limiter
from api.validators import validate_image_upload
from config.settings import settings
from core.blend_color import Colors
from services.param_search_service import (
    FixedParams,
    ParamSearchConfig,
    ParamSearchService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Param Search"])

# ---------------------------------------------------------------------------
# In-memory progress store
# ---------------------------------------------------------------------------

class ProgressStore:
    """Thread-safe store mapping job_id → asyncio.Queue of ProgressEvent."""

    _TTL = 600  # 10 minutes

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._created: dict[str, float] = {}

    def create(self, job_id: str) -> asyncio.Queue:
        self._queues[job_id] = asyncio.Queue()
        self._created[job_id] = time.monotonic()
        self._evict()
        return self._queues[job_id]

    def get(self, job_id: str) -> Optional[asyncio.Queue]:
        return self._queues.get(job_id)

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, t in self._created.items() if now - t > self._TTL]
        for k in expired:
            self._queues.pop(k, None)
            self._created.pop(k, None)


_progress_store = ProgressStore()


# ---------------------------------------------------------------------------
# POST /api/param-search
# ---------------------------------------------------------------------------

@router.post("/param-search", response_model=ParamSearchResponse)
@limiter.limit("2/minute")
@handle_api_errors("running param search")
async def api_param_search(
    request: Request,
    image: UploadFile = File(...),
    preset: Optional[str] = Form(None),
    filamentColors: Optional[str] = Form(None),
    mode: str = Form("pixel"),
    strategy: str = Form("grid"),
    n_trials: int = Form(50),
    seed: Optional[int] = Form(None),
    layer_count: int = Form(4, ge=1, le=10),
    layer_height: float = Form(0.08, gt=0, le=10),
    pixel_size: float = Form(0.42, gt=0, le=10),
    white_backing_layers: int = Form(1, ge=0, le=5),
    max_colors: int = Form(10, ge=1, le=256),
    color_threshold: float = Form(50, ge=0, le=1000),
    detail_size: float = Form(0.42, ge=0.2, le=0.9),
    num_colors: int = Form(8, ge=1, le=256),
    epsilon: float = Form(2.0, gt=0, le=100),
    min_area: float = Form(4.0, gt=0, le=100),
    top_n: int = Form(10, ge=1, le=50),
):
    """Run parameter search and return top-N results sorted by MAE."""
    image_bytes = await image.read()
    validate_image_upload(image.filename, image_bytes)

    # Resolve colors: filamentColors > preset > default (Phase 6 CMYWK).
    # Lets the search run against exactly what the user has selected in the
    # UI, including fully custom filament configurations.
    parsed_preset, parsed_colors = parse_filament_form_payload(preset, filamentColors)
    colors = get_colors_from_request(parsed_preset, parsed_colors)
    job_id = str(uuid.uuid4())
    queue = _progress_store.create(job_id)

    config = ParamSearchConfig(
        mode=mode,
        strategy=strategy,
        n_trials=n_trials,
        seed=seed,
        fixed=FixedParams(
            layer_count=layer_count,
            layer_height=layer_height,
            pixel_size=pixel_size,
            white_backing_layers=white_backing_layers,
        ),
        colors=colors,
        param_ranges=None,
        top_n=top_n,
        baseline_params={
            "pixel": {
                "max_colors": max_colors,
                "color_threshold": color_threshold,
                "detail_size": detail_size,
            },
            "svg": {
                "num_colors": num_colors,
                "epsilon": epsilon,
                "min_area": min_area,
                "detail_size": detail_size,
            },
        },
    )

    loop = asyncio.get_event_loop()

    def _on_progress(event: ProgressEvent) -> None:
        event_with_id = ProgressEvent(
            job_id=job_id,
            completed=event.completed,
            total=event.total,
            best_mae=event.best_mae,
            status=event.status,
            error=event.error,
        )
        loop.call_soon_threadsafe(queue.put_nowait, event_with_id)

    start = time.monotonic()
    service = ParamSearchService(config)

    # Run in thread pool to avoid blocking the event loop
    results = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: service.run_with_timeout(
            image_bytes,
            timeout_seconds=settings.param_search_budget_seconds,
            on_progress=_on_progress,
        ),
    )

    elapsed = time.monotonic() - start

    # Signal completion
    final_event = ProgressEvent(
        job_id=job_id,
        completed=sum(1 for _ in []),  # placeholder
        total=0,
        best_mae=results[0].mae if results else 0.0,
        status="complete",
    )
    queue.put_nowait(final_event)

    if not results:
        raise HTTPException(status_code=422, detail="Search produced zero valid results.")

    result_items = [
        SearchResultItem(
            rank=r.rank,
            mode=r.mode,
            params=r.params,
            mae=r.mae,
            preview_image=r.preview_data_url,
        )
        for r in results[:top_n]
    ]

    logger.info(
        "Param search complete: job_id=%s mode=%s strategy=%s results=%d elapsed=%.1fs",
        job_id, mode, strategy, len(result_items), elapsed,
    )

    return ParamSearchResponse(
        job_id=job_id,
        results=result_items,
        total_evaluated=len(results),
        elapsed_seconds=round(elapsed, 2),
    )


# ---------------------------------------------------------------------------
# GET /api/param-search/progress/{job_id}
# ---------------------------------------------------------------------------

@router.get("/param-search/progress/{job_id}")
async def api_param_search_progress(job_id: str):
    """SSE stream of ProgressEvent objects for a running search job."""
    queue = _progress_store.get(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    async def event_generator():
        while True:
            try:
                event: ProgressEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {event.model_dump_json()}\n\n"
                if event.status in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                # Send keep-alive comment
                yield ": keep-alive\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
