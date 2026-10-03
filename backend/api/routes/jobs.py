"""Heavy-job lifecycle endpoints: poll a queued/running job, fetch its result,
cancel it while queued.

Jobs are created only by the heavy endpoints themselves (via
api/concurrency.run_heavy); these routes observe and control them.
"""
import logging
import time

from fastapi import APIRouter, HTTPException

from api.concurrency import CANCELLED, DONE, RUNNING, get_gate
from api.error_handlers import handle_api_errors

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["Heavy Jobs"])


@router.get("/{job_id}")
@handle_api_errors("reading heavy job status")
async def api_job_status(job_id: str):
    """Queue position while queued, progress while running, outcome when settled."""
    job = get_gate().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown jobId: {job_id}")
    job.last_polled = time.monotonic()
    return job.snapshot()


@router.get("/{job_id}/result")
@handle_api_errors("fetching heavy job result")
async def api_job_result(job_id: str):
    """Fetch a finished job's response (JSON payload or downloaded file)."""
    gate = get_gate()
    job = gate.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown jobId: {job_id}")
    if job.status != DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job is {job.status}; results are available once it finishes.",
        )
    if job.result is None:
        # One-shot file results are dropped after their first fetch.
        raise HTTPException(
            status_code=410,
            detail="This download was already fetched; submit the export again.",
        )
    response = job.build_response()
    # One-shot downloads free their bytes immediately; JSON results stay
    # pollable until the TTL so a client can re-read them.
    if not job.is_json_result():
        gate.drop_result(job)
    return response


@router.delete("/{job_id}")
@handle_api_errors("cancelling heavy job")
async def api_cancel_job(job_id: str):
    """Cancel a queued job. A running job cannot be stopped (409)."""
    gate = get_gate()
    job = gate.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown jobId: {job_id}")
    status = gate.cancel(job)
    if status == CANCELLED:
        return {"jobId": job.job_id, "status": CANCELLED}
    return {"jobId": job.job_id, "status": status}
