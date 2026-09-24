"""Heavy handlers run in worker threads, so the server keeps answering."""
import asyncio
import threading

import httpx
import pytest

import api.routes.image as image_routes
from main import app


@pytest.mark.asyncio
async def test_health_answers_while_an_image_is_processing(monkeypatch, tiny_png_bytes):
    started = threading.Event()
    release = threading.Event()
    blocked = []

    def slow_process_image(**kwargs):
        started.set()
        # Released only after /api/health has answered. On the event loop this
        # wait would stall the health request until the timeout.
        if not release.wait(timeout=3):
            blocked.append(True)
        raise ValueError("stopped after the slow step")

    monkeypatch.setattr(image_routes, "process_image", slow_process_image)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        slow = asyncio.create_task(client.post(
            "/api/process-image",
            data={"mode": "pixel", "pixelSize": "0.4"},
            files={"image": ("tiny.png", tiny_png_bytes, "image/png")},
        ))
        while not started.is_set():
            await asyncio.sleep(0.01)
        health = await client.get("/api/health")
        release.set()
        await slow

    assert health.status_code == 200
    assert not blocked, "health could not be served while an image was processing"
