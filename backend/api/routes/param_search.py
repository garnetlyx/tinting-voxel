"""Full-resolution parameter search jobs and incremental result retrieval."""
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile

from api.error_handlers import handle_api_errors
from api.filament_payload import get_colors_from_request, parse_filament_form_payload, resolve_layer_height
from api.models import (
    ParamSearchResponse,
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
    SearchResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Param Search"])

# ---------------------------------------------------------------------------
# Jobs are kept in this process. Production runs one Uvicorn worker. Admit only
# one unfinished job, so the single-worker executor never accumulates a queue.
# ---------------------------------------------------------------------------

class SearchJob:
    def __init__(self, job_id: str, total: int) -> None:
        self.job_id = job_id
        self.total = total
        self.cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._results: list[SearchResultItem] = []
        self._candidate_errors: list[tuple[int, str]] = []
        self._status = "running"
        self._error: Optional[str] = None
        self.finished_at: Optional[float] = None
        self.last_polled = time.monotonic()

    def touch(self) -> None:
        self.last_polled = time.monotonic()

    def abandoned(self) -> bool:
        return time.monotonic() - self.last_polled > settings.param_search_abandon_seconds

    def add_result(self, result: SearchResult) -> None:
        item = SearchResultItem(
            candidate_id=result.candidate_id,
            is_baseline=result.is_baseline,
            mode=result.mode,
            params=result.params,
            preview_image=result.preview_data_url,
        )
        with self._lock:
            if self._status == "running":
                self._results.append(item)

    def finish(self, error: Optional[str] = None) -> None:
        with self._lock:
            if self._status == "running":
                self._status = "error" if error else "complete"
                self._error = error
            self.finished_at = time.monotonic()

    def add_candidate_error(self, candidate_id: int, reason: str) -> None:
        with self._lock:
            if self._status == "running":
                self._candidate_errors.append((candidate_id, reason))

    def candidate_errors(self) -> list[tuple[int, str]]:
        with self._lock:
            return list(self._candidate_errors)

    def cancel(self) -> None:
        self.cancel_event.set()
        with self._lock:
            if self._status == "running":
                self._status = "cancelled"

    def snapshot(self, after: int = 0) -> ParamSearchResponse:
        with self._lock:
            return ParamSearchResponse(
                job_id=self.job_id,
                completed=len(self._results),
                total=self.total,
                status=self._status,
                settled=self.finished_at is not None,
                error=self._error,
                results=[result for result in self._results if result.candidate_id > after],
            )


class SearchJobStore:
    """Thread-safe job registry; terminal snapshots remain available for 10 minutes."""

    _TTL = 600  # 10 minutes

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, SearchJob] = {}

    def create(self, total: int) -> SearchJob:
        with self._lock:
            self._evict_locked()
            if any(job.finished_at is None for job in self._jobs.values()):
                raise HTTPException(
                    status_code=503,
                    detail="A search is already running. Cancel it or wait for it to finish.",
                )
            job = SearchJob(str(uuid.uuid4()), total)
            self._jobs[job.job_id] = job
            return job

    def get(self, job_id: str) -> Optional[SearchJob]:
        with self._lock:
            self._evict_locked()
            return self._jobs.get(job_id)

    def available(self) -> bool:
        with self._lock:
            self._evict_locked()
            return all(job.finished_at is not None for job in self._jobs.values())

    def _evict_locked(self) -> None:
        now = time.monotonic()
        expired = [
            job_id for job_id, job in self._jobs.items()
            if job.finished_at is not None and now - job.finished_at > self._TTL
        ]
        for job_id in expired:
            del self._jobs[job_id]


_job_store = SearchJobStore()
_search_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="param-search")


def _execute_search(job: SearchJob, service: ParamSearchService, image_bytes: bytes) -> None:
    started = time.monotonic()

    def stop_if_abandoned() -> None:
        if job.abandoned() and not job.cancel_event.is_set():
            logger.info("Param search abandoned by its client: job_id=%s", job.job_id)
            job.cancel()

    def on_result(result: SearchResult) -> None:
        job.add_result(result)
        stop_if_abandoned()

    def on_candidate_error(candidate_id: int, reason: str) -> None:
        job.add_candidate_error(candidate_id, reason)
        stop_if_abandoned()

    try:
        results = service.run(
            image_bytes,
            on_result=on_result,
            on_candidate_error=on_candidate_error,
            cancel=job.cancel_event,
            budget_seconds=settings.param_search_job_budget_seconds,
        )
        failures = job.candidate_errors()
        if job.cancel_event.is_set():
            job.finish()
        elif len(results) + len(failures) < job.total or failures:
            if len(results) + len(failures) < job.total:
                message = f"Search stopped after {settings.param_search_job_budget_seconds:g}s; "
            else:
                message = "Search finished with candidate errors; "
            message += f"{len(results)} of {job.total} previews completed."
            if failures:
                examples = "; ".join(
                    f"option {candidate_id}: {reason}" for candidate_id, reason in failures[:3]
                )
                message += f" {len(failures)} candidate(s) failed: {examples}"
            job.finish(error=message)
        else:
            job.finish()
        logger.info(
            "Param search finished: job_id=%s status=%s completed=%d total=%d elapsed=%.1fs",
            job.job_id, job.snapshot().status, job.snapshot().completed,
            job.total, time.monotonic() - started,
        )
    except Exception as exc:
        logger.exception("Param search failed: job_id=%s", job.job_id)
        job.finish(error=f"Search stopped; {job.snapshot().completed} of {job.total} previews completed. {exc}")


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
    mode: str = Form("pixel", pattern=r"^(pixel|svg|both)$"),
    strategy: str = Form("grid", pattern=r"^(grid|random)$"),
    n_trials: int = Form(50, ge=1, le=500),
    seed: Optional[int] = Form(None),
    layer_count: int = Form(4, ge=1, le=10),
    layer_height: Optional[float] = Form(None, gt=0, le=10),
    pixel_size: float = Form(0.42, gt=0, le=10),
    white_backing_layers: int = Form(3, ge=0, le=5),
    backing_mode: str = Form("white", pattern=r'^(white|black)$'),
    max_colors: int = Form(10, ge=1, le=1024),
    color_threshold: float = Form(50, ge=0, le=1000),
    detail_size: float = Form(0.42, ge=0.2, le=0.9),
    num_colors: int = Form(8, ge=1, le=256),
    epsilon: float = Form(2.0, gt=0, le=100),
    min_area: float = Form(4.0, gt=0, le=100),
):
    """Render alternatives using the current image and print configuration."""
    image_bytes = await image.read()
    validate_image_upload(image.filename, image_bytes)

    # Resolve colors: filamentColors > preset > default (Bambu CMYWK).
    # Lets the search run against exactly what the user has selected in the
    # UI, including fully custom filament configurations.
    parsed_preset, parsed_colors = parse_filament_form_payload(preset, filamentColors)
    colors = get_colors_from_request(parsed_preset, parsed_colors)
    layer_height = resolve_layer_height(layer_height, colors)
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
            backing_mode=backing_mode,
        ),
        colors=colors,
        param_ranges=None,
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

    service = ParamSearchService(config)
    job = _job_store.create(service.total_candidates())
    try:
        _search_executor.submit(_execute_search, job, service, image_bytes)
    except RuntimeError as exc:
        job.finish(error="Search worker unavailable.")
        raise HTTPException(status_code=503, detail="Search worker unavailable.") from exc
    return job.snapshot()


# ---------------------------------------------------------------------------
# GET/DELETE /api/param-search/progress/{job_id}
# ---------------------------------------------------------------------------

@router.get("/param-search/availability")
def api_param_search_availability():
    """Report whether the one search worker can accept a new job."""
    return {"available": _job_store.available()}

@router.get("/param-search/progress/{job_id}", response_model=ParamSearchResponse)
def api_param_search_progress(job_id: str, after: int = Query(0, ge=0)):
    """Return newly completed candidates and current job status."""
    job = _job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    job.touch()
    return job.snapshot(after=after)


@router.delete("/param-search/progress/{job_id}", response_model=ParamSearchResponse)
def api_cancel_param_search(job_id: str):
    """Stop after the current candidate; ignore an in-flight result."""
    job = _job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    job.cancel()
    return job.snapshot()
