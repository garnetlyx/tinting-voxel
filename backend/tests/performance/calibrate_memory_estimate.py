"""Single-job RSS deltas for calibrating services/memory_estimate.py.

Manual run against a local server:
    HEAVY_JOB_CONCURRENCY=1 RATE_LIMIT_ENABLED=false \
        .venv/bin/python -m uvicorn main:app --port 8020
    .venv/bin/python tests/performance/calibrate_memory_estimate.py

2026-10 measurements: process_image 2M cells 5x10 -> 1559 MB (before this
calibration the constants priced it at 476 MB); filament_preview 5^8 full
-> 237 MB; 5^9 paginated -> 3 MB. Keep the constants conservative (over-
estimating asks the user earlier; under-estimating crashes the server).
"""
import io
import sys
import time

import numpy as np
import psutil
import requests
from PIL import Image

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8020"


def server_proc():
    for proc in psutil.process_iter(["cmdline", "name"]):
        cmdline = proc.info["cmdline"] or []
        if "python" not in (proc.info["name"] or "").lower():
            continue
        if any("uvicorn" in p for p in cmdline) and any("8020" in p for p in cmdline):
            return psutil.Process(proc.pid)
    raise SystemExit("server not found")


def peak_delta(fn) -> float:
    proc = server_proc()
    import gc as _gc
    time.sleep(1.0)
    baseline = proc.memory_info().rss
    stop = time.time() + 60
    peak = baseline
    import threading
    def watch():
        nonlocal peak
        while time.time() < stop:
            peak = max(peak, proc.memory_info().rss)
            time.sleep(0.05)
    t = threading.Thread(target=watch, daemon=True)
    t.start()
    started = time.perf_counter()
    result = fn()
    took = time.perf_counter() - started
    time.sleep(0.5)
    return peak - baseline, took, result


def noisy_jpeg(width=3000, height=1300) -> bytes:
    rng = np.random.default_rng(7)
    array = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(array).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


img = noisy_jpeg()

def run_process():
    r = requests.post(
        f"{BASE}/api/process-image",
        files={"image": ("calib.jpg", img, "image/jpeg")},
        data={"mode": "pixel", "pixelSize": "0.09", "maxColors": "10", "colorThreshold": "50",
              "layerCount": "10", "filamentPreset": "bambu_cmywk", "whiteBackingLayers": "3"},
        timeout=600,
    )
    return r.status_code

def run_preview_8():
    return requests.post(f"{BASE}/api/filament-preview",
                         json={"filamentPreset": "bambu_cmywk", "layerCount": 8}, timeout=600).status_code

def run_preview_9_paged():
    return requests.post(f"{BASE}/api/filament-preview",
                         json={"filamentPreset": "bambu_cmywk", "layerCount": 9, "page": 1, "pageSize": 10000},
                         timeout=600).status_code

requests.get(f"{BASE}/api/health", timeout=10).raise_for_status()

for name, fn, predicted in [
    ("process_image 2M cells 5x10", run_process, 476),
    ("filament_preview 5^8 full", run_preview_8, 337),
    ("filament_preview 5^9 paged10k", run_preview_9_paged, 62),
]:
    delta, took, status = peak_delta(fn)
    print(f"{name:32s} status={status} took={took:5.1f}s delta={delta/1e6:7.0f} MB  predicted={predicted} MB")
