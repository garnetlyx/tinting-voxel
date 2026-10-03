"""Unit tests for the heavy-job gate (api/concurrency.py)."""
import asyncio
import json
import threading

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response

from api.concurrency import (
    CANCELLED,
    DONE,
    ERROR,
    QUEUED,
    RUNNING,
    HeavyGate,
    ServiceBusyError,
)
from config.settings import settings



async def await_thread_event(event: threading.Event, timeout: float = 5.0) -> None:
    """Wait for a threading.Event without blocking the event loop."""
    import time
    deadline = time.monotonic() + timeout
    while not event.is_set():
        assert time.monotonic() < deadline, "thread event never set"
        await asyncio.sleep(0.005)


def _ok_job(marker: str = "ok", delay: float = 0.0, started=None, finished=None):
    def job() -> Response:
        if started is not None:
            started.set()
        if delay:
            import time
            time.sleep(delay)
        if finished is not None:
            finished.wait(timeout=5)
        return Response(content=f'{{"marker": "{marker}"}}', media_type="application/json")
    return job


@pytest.fixture
def gate(monkeypatch):
    """A fresh gate with one slot, isolated from the app's registry."""
    monkeypatch.setattr(settings, "heavy_job_concurrency", 1)
    monkeypatch.setattr(settings, "heavy_job_max_queue", 3)
    monkeypatch.setattr(settings, "heavy_job_result_ttl_seconds", 600.0)
    return HeavyGate()

async def drain_executions(gate: HeavyGate, timeout: float = 10.0) -> None:
    """Keep the loop alive until every execution task finished its worker.

    A thread that outlives its event loop cannot report its result or receive
    anyio's shutdown sentinel, leaving a non-daemon thread that hangs process
    exit (CI: the backend job idled 6h until cancelled).
    """
    import time as _time
    deadline = _time.monotonic() + timeout
    while gate.executions or gate.queue:
        assert _time.monotonic() < deadline, "gate executions did not drain"
        await asyncio.sleep(0.005)


@pytest.fixture(autouse=True)
async def drain_gate_after_test(gate):
    """No worker thread may outlive the test's event loop."""
    yield
    await drain_executions(gate)


@pytest.mark.asyncio
async def test_idle_submission_runs_inline(gate):
    response = await gate.run_heavy("test", _ok_job("direct"))
    assert response.status_code == 200
    assert b'"direct"' in response.body
    # Inline jobs never enter the registry: their response leaves with the
    # caller, so nothing is retained for the TTL (review F1).
    assert not gate.jobs


@pytest.mark.asyncio
async def test_second_submission_queues_with_position(gate):
    first_started = threading.Event()
    release_first = threading.Event()

    async def submit(marker, fn):
        return await gate.run_heavy(marker, fn)

    first = asyncio.create_task(submit("first", _ok_job("first", started=first_started, finished=release_first)))
    await await_thread_event(first_started)
    assert gate.running == 1

    second = asyncio.create_task(submit("second", _ok_job("second")))
    response = await second
    assert response.status_code == 202
    import json as _json
    payload = _json.loads(response.body)
    assert payload["position"] == 1
    assert payload["status"] == "queued"

    release_first.set()
    inline_first = await first
    assert inline_first.status_code == 200
    assert b'"first"' in inline_first.body


@pytest.mark.asyncio
async def test_queue_drains_in_fifo_order(gate):
    order = []
    started = threading.Event()
    release = threading.Event()

    first = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)

    queued = [
        asyncio.create_task(gate.run_heavy(kind, _ok_job(kind)))
        for kind in ("b", "c")
    ]
    await asyncio.sleep(0.05)  # let both enqueue
    release.set()
    await first
    responses = await asyncio.gather(*queued)
    # All queued jobs were admitted as jobs, not run inline (the inline first
    # job is not registered).
    assert all(r.status_code == 202 for r in responses)
    # Let the dispatcher drain; the queued jobs finished, strictly after the
    # inline one and each other (the slot serializes them).
    await asyncio.sleep(0.15)
    queued_jobs = list(gate.jobs.values())
    assert [j.status for j in queued_jobs] == [DONE, DONE]
    assert queued_jobs[0].started_at >= queued_jobs[0].created_at
    assert queued_jobs[1].started_at >= queued_jobs[0].finished_at


@pytest.mark.asyncio
async def test_queue_full_raises_service_busy(gate):
    started = threading.Event()
    release = threading.Event()
    first = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)

    queued = [asyncio.create_task(gate.run_heavy(kind, _ok_job(kind))) for kind in ("b", "c", "d")]
    await asyncio.sleep(0.05)
    with pytest.raises(ServiceBusyError) as exc_info:
        await gate.run_heavy("e", _ok_job("e"))
    assert exc_info.value.retry_after > 0

    release.set()
    await first
    await asyncio.gather(*queued)


@pytest.mark.asyncio
async def test_cancel_queued_job(gate):
    started = threading.Event()
    release = threading.Event()
    first = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)

    accepted = await gate.run_heavy("b", _ok_job("b"))
    job_id = json.loads(accepted.body)["jobId"]

    assert gate.cancel(gate.jobs[job_id]) == CANCELLED
    assert gate.jobs[job_id].status == CANCELLED
    assert not gate.queue  # removed from the queue

    release.set()
    await first


@pytest.mark.asyncio
async def test_cancel_running_job_is_refused(gate):
    started = threading.Event()
    release = threading.Event()
    release_b = threading.Event()
    blocker = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)
    accepted = await gate.run_heavy("b", _ok_job("b", finished=release_b))
    job = gate.jobs[json.loads(accepted.body)["jobId"]]
    release.set()
    await blocker
    # b now holds the slot; cancelling it must be refused.
    for _ in range(200):
        if job.status == RUNNING:
            break
        await asyncio.sleep(0.01)
    assert job.status == RUNNING
    with pytest.raises(HTTPException) as exc_info:
        gate.cancel(job)
    assert exc_info.value.status_code == 409
    release_b.set()
    await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_inline_job_reraises_original_exception(gate):
    def broken() -> Response:
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        await gate.run_heavy("broken", broken)


@pytest.mark.asyncio
async def test_queued_job_error_surfaces_with_status(gate):
    started = threading.Event()
    release = threading.Event()
    first = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)

    def broken() -> Response:
        raise ValueError("queued failure")

    accepted = await gate.run_heavy("b", broken)  # fails fast once admitted
    job = gate.jobs[json.loads(accepted.body)["jobId"]]
    release.set()
    await first
    await asyncio.sleep(0.1)
    assert job.status == ERROR
    assert job.error_status == 422
    assert "queued failure" in job.error


@pytest.mark.asyncio
async def test_expired_results_are_evicted(gate, monkeypatch):
    import time as _time
    monkeypatch.setattr(settings, "heavy_job_result_ttl_seconds", 0.0)
    started = threading.Event()
    release = threading.Event()
    blocker = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)
    accepted = await gate.run_heavy("b", _ok_job("b"))
    job = gate.jobs[json.loads(accepted.body)["jobId"]]
    release.set()
    await blocker
    for _ in range(100):
        if job.status == DONE:
            break
        await asyncio.sleep(0.01)
    job.finished_at = _time.monotonic() - 1
    gate._evict()
    assert not gate.jobs


@pytest.mark.asyncio
async def test_file_result_dropped_after_fetch(gate):
    def file_job() -> Response:
        return Response(content=b"PK-zip-bytes", media_type="application/zip")

    started = threading.Event()
    release = threading.Event()
    blocker = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)
    accepted = await gate.run_heavy("download", file_job)
    job = gate.jobs[json.loads(accepted.body)["jobId"]]
    release.set()
    await blocker
    for _ in range(100):
        if job.status == DONE:
            break
        await asyncio.sleep(0.01)
    assert not job.is_json_result()
    replayed = job.build_response()
    gate.drop_result(job)
    assert job.result is None


@pytest.mark.asyncio
async def test_abandoned_queued_job_is_skipped(gate, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    first = asyncio.create_task(gate.run_heavy("a", _ok_job("a", started=started, finished=release)))
    await await_thread_event(started)

    accepted = await gate.run_heavy("b", _ok_job("b"))
    job = gate.jobs[json.loads(accepted.body)["jobId"]]
    # Simulate a client that stopped polling long ago.
    import time
    job.last_polled = time.monotonic() - 1000

    release.set()
    await first
    await asyncio.sleep(0.1)
    assert job.status == CANCELLED
