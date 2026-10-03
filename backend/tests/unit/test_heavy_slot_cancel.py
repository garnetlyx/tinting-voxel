"""Regression: native asyncio cancellation must not release a busy slot early.

Verified failure mode (review F2): a plain ``await run_in_threadpool`` let a
native task cancellation decrement the slot while the worker thread was still
running, admitting overlapping GB-scale jobs. The execution-task + shield
structure in api/concurrency.py is what this test protects.
"""
import asyncio
import threading

import pytest
from fastapi.responses import Response

from api.concurrency import HeavyGate
from config.settings import settings


@pytest.mark.asyncio
async def test_native_cancel_keeps_slot_until_thread_finishes(monkeypatch):
    monkeypatch.setattr(settings, "heavy_job_concurrency", 1)
    monkeypatch.setattr(settings, "heavy_job_max_queue", 3)
    gate = HeavyGate()

    thread_started = threading.Event()
    release_thread = threading.Event()
    observed: list[int] = []

    def blocking_job() -> Response:
        thread_started.set()
        release_thread.wait(timeout=5)
        return Response(content=b'{"ok": true}', media_type="application/json")

    task = asyncio.get_running_loop().create_task(gate.run_heavy("blocked", blocking_job))
    await asyncio.sleep(0.05)
    assert thread_started.is_set()

    # Native cancellation, as uvicorn does on client disconnect.
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    await asyncio.sleep(0.1)
    observed.append(gate.running)
    assert gate.running == 1, "slot released while the worker thread still runs"

    # A second job must not be admitted inline while the thread lives.
    assert not gate._can_run_inline()

    release_thread.set()
    await asyncio.sleep(0.2)
    assert gate.running == 0
    # The cancelled inline job never entered the registry.
    assert not gate.jobs
