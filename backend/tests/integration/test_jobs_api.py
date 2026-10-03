"""Integration tests for heavy-job queuing and the memory-budget backstop."""
import asyncio
import json
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

import api.concurrency as concurrency_module
from api.concurrency import HeavyGate
from config.settings import settings
from main import app
from services.filament_preview import FilamentPreviewService

PREVIEW_BODY = {
    "filamentPreset": "bambu_cmyw",
    "layerCount": 4,
}


@pytest.fixture(autouse=True)
async def fresh_gate(monkeypatch):
    """Isolate the app's heavy-job registry and budgets per test, and drain
    every worker before the loop closes (non-daemon threads hang exit)."""
    monkeypatch.setattr(concurrency_module, "_gate", HeavyGate())
    monkeypatch.setattr(settings, "heavy_job_concurrency", 1)
    monkeypatch.setattr(settings, "heavy_job_max_queue", 8)
    yield
    import time as _time
    gate = concurrency_module._gate
    deadline = _time.monotonic() + 10
    while gate.executions or gate.queue:
        assert _time.monotonic() < deadline, "gate executions did not drain"
        await asyncio.sleep(0.005)


def test_small_preview_runs_inline(client):
    """The idle fast path answers directly; inline jobs never register."""
    response = client.post("/api/filament-preview", json=PREVIEW_BODY)
    assert response.status_code == 200
    assert "colorMatrix" in response.json()
    assert not concurrency_module._gate.jobs


@pytest.mark.asyncio
async def test_busy_server_queues_then_delivers(monkeypatch):
    """A second request while a job runs is admitted (202), polled, fetched."""
    started = threading.Event()
    release = threading.Event()

    def slow_preview(self, page=None, page_size=None):
        started.set()
        assert release.wait(timeout=5)
        return {
            "image": "x", "colorMatrix": [{"code": "A", "rgb": [1, 2, 3]}],
            "stats": {"colorCount": 4, "combinationCount": 1},
            "imageDimensions": {"width": 1, "height": 1},
        }

    monkeypatch.setattr(FilamentPreviewService, "generate_preview", slow_preview)
    monkeypatch.setattr(FilamentPreviewService, "check_similar_colors", lambda self, threshold=10.0: [])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/filament-preview", json=PREVIEW_BODY))
        while not started.is_set():
            await asyncio.sleep(0.005)

        second = await client.post("/api/filament-preview", json=PREVIEW_BODY)
        assert second.status_code == 202
        job_id = second.json()["jobId"]
        assert second.json()["position"] == 1

        status = await client.get(f"/api/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
        assert status.json()["position"] == 1

        release.set()
        assert (await first).status_code == 200

        for _ in range(100):
            snapshot = (await client.get(f"/api/jobs/{job_id}")).json()
            if snapshot["status"] == "done":
                break
            await asyncio.sleep(0.02)
        assert snapshot["status"] == "done"
        assert snapshot["resultKind"] == "json"

        result = await client.get(f"/api/jobs/{job_id}/result")
        assert result.status_code == 200
        assert result.json()["stats"]["combinationCount"] == 1


@pytest.mark.asyncio
async def test_queued_job_can_be_cancelled(monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow_preview(self, page=None, page_size=None):
        started.set()
        assert release.wait(timeout=5)
        return {
            "image": "x", "colorMatrix": [],
            "stats": {"colorCount": 4, "combinationCount": 1},
            "imageDimensions": {"width": 1, "height": 1},
        }

    monkeypatch.setattr(FilamentPreviewService, "generate_preview", slow_preview)
    monkeypatch.setattr(FilamentPreviewService, "check_similar_colors", lambda self, threshold=10.0: [])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/filament-preview", json=PREVIEW_BODY))
        while not started.is_set():
            await asyncio.sleep(0.005)

        second = await client.post("/api/filament-preview", json=PREVIEW_BODY)
        job_id = second.json()["jobId"]

        cancelled = await client.delete(f"/api/jobs/{job_id}")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        snapshot = (await client.get(f"/api/jobs/{job_id}")).json()
        assert snapshot["status"] == "cancelled"

        release.set()
        assert (await first).status_code == 200


@pytest.mark.asyncio
async def test_running_job_cannot_be_stopped(monkeypatch):
    import itertools
    started = threading.Event()
    release = threading.Event()
    release_second = threading.Event()
    calls = itertools.count()

    def slow_preview(self, page=None, page_size=None):
        if next(calls) == 0:
            started.set()
            assert release.wait(timeout=5)
        else:
            assert release_second.wait(timeout=5)
        return {
            "image": "x", "colorMatrix": [],
            "stats": {"colorCount": 4, "combinationCount": 1},
            "imageDimensions": {"width": 1, "height": 1},
        }

    monkeypatch.setattr(FilamentPreviewService, "generate_preview", slow_preview)
    monkeypatch.setattr(FilamentPreviewService, "check_similar_colors", lambda self, threshold=10.0: [])

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        first = asyncio.create_task(client.post("/api/filament-preview", json=PREVIEW_BODY))
        while not started.is_set():
            await asyncio.sleep(0.005)

        # Queue a second job; once it is running, cancelling must be refused.
        second = await client.post("/api/filament-preview", json=PREVIEW_BODY)
        job_id = second.json()["jobId"]
        release.set()
        assert (await first).status_code == 200
        for _ in range(200):
            snapshot = (await client.get(f"/api/jobs/{job_id}")).json()
            if snapshot.get("status") == "running":
                break
            await asyncio.sleep(0.01)
        refused = await client.delete(f"/api/jobs/{job_id}")
        assert refused.status_code == 409
        release_second.set()


def test_oversize_backstop_refuses_then_forces(client, monkeypatch):
    """Over-budget jobs get a structured 422; forceOversize runs them."""
    monkeypatch.setattr(settings, "heavy_memory_budget_mb", 0.001)

    refused = client.post("/api/filament-preview", json=PREVIEW_BODY)
    assert refused.status_code == 422
    detail = refused.json()["detail"]
    assert detail["code"] == "job_too_large"
    assert detail["budgetMb"] == 0
    assert "suggestion" in detail

    forced = client.post(
        "/api/filament-preview", json={**PREVIEW_BODY, "forceOversize": True},
    )
    assert forced.status_code == 200
    assert "colorMatrix" in forced.json()


def test_estimate_endpoint_shapes(client):
    response = client.post("/api/v2/estimate-job", json={
        "kind": "filament_preview",
        "filamentPreview": {"layerCount": 10},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "filament_preview"
    assert body["budgetMb"] > 0
    assert isinstance(body["withinBudget"], bool)
    # 4 colors x 10 layers over the default budget: a suggestion must come back.
    if not body["withinBudget"]:
        assert body["suggestion"]["pageSize"] == 10000

    process = client.post("/api/v2/estimate-job", json={
        "kind": "process_image",
        "processImage": {
            "mode": "pixel", "imageWidth": 2000, "imageHeight": 1000,
            "pixelSize": 0.1, "layerCount": 8, "maxColors": 10,
        },
    })
    assert process.status_code == 200
    assert process.json()["estimatedMb"] > 0

    malformed = client.post("/api/v2/estimate-job", json={"kind": "download"})
    assert malformed.status_code == 422


def test_unknown_job_is_404(client):
    assert client.get("/api/jobs/none").status_code == 404
    assert client.delete("/api/jobs/none").status_code == 404
    assert client.get("/api/jobs/none/result").status_code == 404
