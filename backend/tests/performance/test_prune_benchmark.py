"""
Real-image benchmark: process_image with the Clear CMYWG palette at 8 layers
and 0.84 mm layer height — the frozen headline case — timed on both mapping
paths with identical inputs:

- pruned: automatic transparency classification (composition-pruned matrix)
- oracle: forced full enumeration by raising the transparency threshold so
  that nothing classifies as translucent

Both calls go through the complete pipeline (K-means extraction, mapping,
simulated-print rendering). The pruned path must complete strictly faster at
equal output quality (the mapping-quality budgets are asserted separately in
TestPrunedVsFullOracle; here we assert pipeline success and the speedup).
Metrics are written to the OS temp dir, never the working tree.
"""
import os
import tempfile
import time

import numpy as np
import pytest
from skimage.color import deltaE_ciede2000, rgb2lab

from config.settings import settings
from core.color_config import get_preset
from core.color_materials import Colors
from services.image_processor import process_image

LOCAL_PHOTO = os.path.join(
    os.path.dirname(__file__), "..", "..", "tests", "fixtures", "images-local", "local-photo.JPG"
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(LOCAL_PHOTO), reason="local-photo.JPG local fixture not present"
)


def _lab(rgb):
    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return rgb2lab(arr).reshape(-1, 3)


def test_clear_8l_process_image_pruned_vs_full_enumeration_benchmark():
    colors = Colors.from_configs(get_preset("clear_cmywg"))
    image_bytes = open(LOCAL_PHOTO, "rb").read()
    common = dict(
        image_bytes=image_bytes,
        max_colors=16,
        color_threshold=50,
        pixel_size=0.42,
        filament_colors=colors,
        layer_count=8,
        layer_height=0.84,
        white_backing_layers=1,
        detail_size=0.42,
    )

    original_threshold = settings.transparent_td_threshold
    try:
        t0 = time.monotonic()
        pruned = process_image(**common)
        t_pruned = time.monotonic() - t0

        settings.transparent_td_threshold = 1_000_000.0  # nothing translucent
        t0 = time.monotonic()
        full = process_image(**common)
        t_full = time.monotonic() - t0
    finally:
        settings.transparent_td_threshold = original_threshold

    assert pruned["colorBlocks"] and full["colorBlocks"]
    assert t_pruned < t_full, (
        f"pruned pipeline ({t_pruned:.1f}s) must beat full enumeration ({t_full:.1f}s)"
    )

    # Output quality: mapped palettes stay perceptually close between paths.
    pr = [(b["r"], b["g"], b["b"]) for b in pruned["colorBlocks"]]
    fr = [(b["r"], b["g"], b["b"]) for b in full["colorBlocks"]]
    assert len(pr) == len(fr)
    de = np.array([
        float(deltaE_ciede2000(_lab([fr[i]]), _lab([pr[i]]), channel_axis=-1).ravel()[0])
        for i in range(len(pr))
    ])

    metrics = {
        "layer_count": 8,
        "layer_height": 0.84,
        "full_enumeration_codes": 5**8,
        "composition_representatives": 495,
        "pruned_process_image_s": round(t_pruned, 2),
        "full_process_image_s": round(t_full, 2),
        "speedup": round(t_full / t_pruned, 1),
        "palette_delta_e00_mean": round(float(de.mean()), 2),
        "palette_delta_e00_max": round(float(de.max()), 2),
    }
    out_path = os.path.join(tempfile.gettempdir(), "prune_benchmark_8L.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        import json

        json.dump(metrics, fh, indent=2)
    print(f"\nbenchmark metrics -> {out_path}: {metrics}")
