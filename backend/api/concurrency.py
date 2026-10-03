"""Single gate for memory-heavy request work.

Every endpoint that allocates GBs (image processing, stack enumeration,
previews, exports) runs through :func:`run_heavy`. The gate keeps at most
``settings.heavy_job_concurrency`` jobs running at once — one job's peak
allocation is what the memory budget is sized against, so serialized jobs
cannot stack into an OOM kill (the 2026-10-02 crash: four concurrent
process-image requests plus a 1.9M-combination preview).

A request that arrives while all slots are busy does not hold its HTTP
connection: it is admitted as a job and answered with 202 ``{jobId, position}``.
The client polls ``GET /api/jobs/{jobId}`` (queue position, then running,
then done) and fetches the finished result from ``GET /api/jobs/{jobId}/result``.
A queued job can be cancelled with ``DELETE /api/jobs/{jobId}`` before it
starts; a running job cannot be stopped (the worker thread owns GBs of numpy
state and runs to completion), which the DELETE reports as 409.

Semantics that make this safe with a single Uvicorn worker:

- The idle fast path runs the job inline in the request, so nothing changes
  for the common one-user case: no job id, no polling. Inline jobs never
  enter the registry — the caller already holds the response, and retaining
  it would pin its payload for the TTL (review F1).
- Slot ownership is an independently referenced execution task. The request
  awaits it through ``asyncio.shield``, so even a native task cancellation
  (uvicorn disconnect) releases the slot only after the worker thread has
  actually finished (review F2: verified a plain await released it early).
- Waiting never runs a thread: a 202 answered request has allocated nothing
  but its registry entry (the request's own payload, already parsed), and
  retained results are bounded by ``heavy_job_result_max_bytes``.
"""
import asyncio
import logging
import time
import uuid
from collections import deque
from typing import Callable, Optional

from fastapi import HTTPException, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from config.settings import settings
from services.telemetry import emit

logger = logging.getLogger(__name__)

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"

# A queued job whose client stopped polling (closed tab, reload) is skipped
# when its turn comes, so an abandoned queue entry cannot spend the slot.
ABANDON_SECONDS = 120.0


class ServiceBusyError(Exception):
    """All heavy-job slots are taken and the queue is full."""

    def __init__(self, retry_after: int = 5):
        self.retry_after = retry_after
        super().__init__("Server busy: heavy-job queue is full. Retry shortly.")


class HeavyJob:
    """One admitted heavy operation and its lifecycle state."""

    def __init__(self, job_id: str, kind: str, fn: Callable[[], Response]) -> None:
        self.job_id = job_id
        self.kind = kind
        self.fn = fn
        self.status = QUEUED
        self.error: Optional[str] = None
        self.error_status: Optional[int] = None
        # The live exception, so the inline fast path can re-raise it through
        # the route's normal error handling (handle_api_errors maps ValueError
        # to 422, HTTPException passes through). Cleared once consumed.
        self.exception: Optional[BaseException] = None
        # (content, media_type, headers) of the built response; set on DONE.
        self.result: Optional[tuple[bytes, str, dict[str, str]]] = None
        self.created_at = time.monotonic()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.last_polled: float = self.created_at
        self.result_fetched = False
        # Strongly referenced execution task; owns the slot until the worker
        # thread finishes, regardless of what happens to the HTTP request.
        self.execution_task: Optional["asyncio.Task[None]"] = None

    def snapshot(self) -> dict:
        """Poll payload: position while queued, timing once settled."""
        out = {
            "jobId": self.job_id,
            "kind": self.kind,
            "status": self.status,
        }
        if self.status == QUEUED:
            out["position"] = _gate.position_of(self)
            out["queueDepth"] = len(_gate.queue)
        if self.status == RUNNING and self.started_at is not None:
            out["runningMs"] = round((time.monotonic() - self.started_at) * 1000)
        if self.status == DONE:
            out["resultKind"] = "json" if self.is_json_result() else "file"
        if self.error is not None:
            out["error"] = self.error[:500]
            out["errorStatus"] = self.error_status or 500
        return out

    def is_json_result(self) -> bool:
        media = self.result[1] if self.result else ""
        return media == "application/json"

    def build_response(self) -> Response:
        """Replay the stored result as a fresh Response."""
        content, media_type, headers = self.result
        return Response(content=content, media_type=media_type, headers=headers)


class HeavyGate:
    """Bounded slot pool plus FIFO queue, driven from the event loop."""

    def __init__(self) -> None:
        self.queue: deque[HeavyJob] = deque()
        self.jobs: dict[str, HeavyJob] = {}
        self.running = 0
        self._dispatcher_alive = False
        # Held so the loop never garbage-collects an in-flight dispatcher.
        self._dispatcher_task: Optional["asyncio.Task[None]"] = None
        self._retained_result_bytes = 0

    # -- submission ---------------------------------------------------------

    def _can_run_inline(self) -> bool:
        return (
            self.running < settings.heavy_job_concurrency
            and not self.queue
            and not self._dispatcher_alive
        )

    async def run_heavy(self, kind: str, fn: Callable[[], Response]) -> Response:
        """Run ``fn`` under the gate; 202-accept it when all slots are busy.

        Returns either the job's response directly (idle fast path) or a 202
        JSONResponse describing the admitted job. Raises ServiceBusyError when
        the queue is full.
        """
        # Check-and-reserve without awaiting in between: no interleaving.
        if self._can_run_inline():
            job = HeavyJob(str(uuid.uuid4()), kind, fn)
            execution = self._launch(job)
            try:
                await asyncio.shield(execution)
            except asyncio.CancelledError:
                # The request went away; the execution task still owns the
                # slot until the worker thread finishes. Nothing to return.
                raise
            return self._finish_inline(job)

        if len(self.queue) >= settings.heavy_job_max_queue:
            emit("heavy_job_rejected", kind=kind, reason="queue_full",
                 queue_depth=len(self.queue))
            raise ServiceBusyError()

        job = HeavyJob(str(uuid.uuid4()), kind, fn)
        self.jobs[job.job_id] = job
        self.queue.append(job)
        emit("heavy_job_queued", kind=kind, position=self.position_of(job),
             queue_depth=len(self.queue))
        self._ensure_dispatcher()
        return JSONResponse(
            status_code=202,
            content={
                "jobId": job.job_id,
                "kind": kind,
                "status": QUEUED,
                "position": self.position_of(job),
                "queueDepth": len(self.queue),
            },
        )

    def _finish_inline(self, job: HeavyJob) -> Response:
        """Fast-path result: the response, or the job's original exception.

        Inline jobs never enter the registry, and their payload closure and
        exception are dropped here — the caller owns both now.
        """
        job.fn = None
        if job.result is not None:
            # The response bytes leave with the caller, not the store.
            self._retained_result_bytes -= len(job.result[0])
        if job.status == ERROR:
            exception, job.exception = job.exception, None
            job.result = None
            if exception is not None:
                raise exception
            raise HTTPException(status_code=500, detail=job.error or "Heavy job failed")
        return job.build_response()

    def _launch(self, job: HeavyJob) -> "asyncio.Task[None]":
        """Start the job's execution task; it alone owns the slot."""
        job.execution_task = asyncio.get_running_loop().create_task(self._execute(job))
        return job.execution_task

    async def _execute(self, job: HeavyJob) -> None:
        """Run one job's function in a worker thread, holding a slot throughout."""
        self.running += 1
        job.status = RUNNING
        job.started_at = time.monotonic()
        waited_ms = round((job.started_at - job.created_at) * 1000)
        emit("heavy_job_started", kind=job.kind, waited_ms=waited_ms,
             queue_depth=len(self.queue))
        started = time.perf_counter()
        try:
            response = await run_in_threadpool(job.fn)
            job.result = (
                response.body if isinstance(response.body, bytes) else bytes(response.body),
                response.media_type or "application/json",
                {k: v for k, v in (response.headers or {}).items()
                 if k.lower() != "content-length"},
            )
            self._retained_result_bytes += len(job.result[0])
            job.status = DONE
        except HTTPException as exc:
            # The job built its own HTTP error; replay it verbatim.
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            payload = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            job.exception = exc
            job.error = detail
            job.error_status = exc.status_code
            job.result = (
                payload.body, "application/json",
                {k: v for k, v in payload.headers.items() if k.lower() != "content-length"},
            )
            job.status = ERROR
        except Exception as exc:  # noqa: BLE001 - surfaced to the polling client
            logger.exception("Heavy job failed: kind=%s job_id=%s", job.kind, job.job_id)
            job.exception = exc
            job.error = f"{type(exc).__name__}: {exc}"
            job.error_status = 422 if isinstance(exc, ValueError) else 500
            job.status = ERROR
        finally:
            job.finished_at = time.monotonic()
            self.running -= 1
            # The payload closure is no longer needed once the job ran.
            job.fn = None
            emit("heavy_job_finished", kind=job.kind, status=job.status,
                 duration_ms=round((time.perf_counter() - started) * 1000))
            self._enforce_result_budget()
            self._evict()

    # -- queue driving ------------------------------------------------------

    def _ensure_dispatcher(self) -> None:
        if not self._dispatcher_alive:
            self._dispatcher_alive = True
            self._dispatcher_task = asyncio.get_running_loop().create_task(self._dispatch())

    async def _dispatch(self) -> None:
        """Admit queued jobs as slots free up; exits when the queue drains."""
        try:
            while self.queue:
                while self.running >= settings.heavy_job_concurrency and self.queue:
                    # Slots are only released by _execute on this loop, so a
                    # short yield is enough to observe the release. Cancellations
                    # can empty the queue while we wait (review F7).
                    await asyncio.sleep(0.05)
                if not self.queue:
                    break
                job = self.queue.popleft()
                if job.status == CANCELLED:
                    continue
                if time.monotonic() - job.last_polled > ABANDON_SECONDS:
                    job.status = CANCELLED
                    job.finished_at = time.monotonic()
                    emit("heavy_job_cancelled", kind=job.kind, reason="abandoned")
                    continue
                # Await the launched task so the next queue entry cannot be
                # admitted before this one holds its slot (FIFO + cap).
                await self._launch(job)
        finally:
            self._dispatcher_alive = False
            self._dispatcher_task = None
            # A submission can land between the last queue check and the flag
            # flip above; re-arm so that job is never stranded.
            if self.queue:
                self._ensure_dispatcher()

    # -- registry -----------------------------------------------------------

    def position_of(self, job: HeavyJob) -> int:
        try:
            return self.queue.index(job) + 1
        except ValueError:
            return 1

    def get(self, job_id: str) -> Optional[HeavyJob]:
        self._evict()
        return self.jobs.get(job_id)

    def cancel(self, job: HeavyJob) -> str:
        """Cancel a queued job; report running jobs as unstoppable."""
        if job.status == QUEUED:
            job.status = CANCELLED
            job.finished_at = time.monotonic()
            try:
                self.queue.remove(job)
            except ValueError:
                pass
            emit("heavy_job_cancelled", kind=job.kind, reason="client")
            return CANCELLED
        if job.status == RUNNING:
            raise HTTPException(
                status_code=409,
                detail="Job is already running and will finish; it cannot be stopped.",
            )
        return job.status

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [
            job_id for job_id, job in self.jobs.items()
            if job.finished_at is not None
            and now - job.finished_at > settings.heavy_job_result_ttl_seconds
        ]
        for job_id in expired:
            self._forget(self.jobs[job_id])

    def _enforce_result_budget(self) -> None:
        """Drop oldest finished results when retained bytes exceed the budget."""
        limit = settings.heavy_job_result_max_bytes
        if self._retained_result_bytes <= limit:
            return
        finished = sorted(
            (job for job in self.jobs.values()
             if job.finished_at is not None and job.result is not None),
            key=lambda job: job.finished_at or 0,
        )
        for job in finished:
            if self._retained_result_bytes <= limit:
                break
            self._drop_result(job)

    def _drop_result(self, job: HeavyJob) -> None:
        if job.result is not None:
            self._retained_result_bytes -= len(job.result[0])
        job.result = None
        job.result_fetched = True

    def _forget(self, job: HeavyJob) -> None:
        self._drop_result(job)
        job.exception = None
        self.jobs.pop(job.job_id, None)

    def drop_result(self, job: HeavyJob) -> None:
        """Free a fetched file result immediately (one-shot downloads)."""
        self._drop_result(job)


_gate = HeavyGate()


def get_gate() -> HeavyGate:
    """The process-wide gate (one Uvicorn worker owns one gate)."""
    return _gate


async def run_heavy(kind: str, fn: Callable[[], Response]) -> Response:
    """Module-level entry point used by routes."""
    return await _gate.run_heavy(kind, fn)
