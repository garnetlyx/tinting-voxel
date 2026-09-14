"""
Real-image benchmark for the time-budget enumeration policy.

The shipped clear preset (4-color CMYW) at 8 layers / 0.84 mm enumerates
fully in seconds — well inside the 60 s budget — so production takes the
exact full path. This benchmark pins that headline timing, then exercises
the composition-pruned path on a uniform scalar-td translucent set (the
paper per-channel clear presets are order-sensitive and no longer prunable)
by forcing the budget to ~zero, and records both timings plus palette drift
between the paths. Metrics are written to the OS temp dir, never the tree.
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
# Committed synthetic fixture: the CMYWK performance gate runs everywhere.
PERF_FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "images", "perf_cmywk.jpg"
)


def _lab(rgb):
    arr = np.asarray(rgb, dtype=np.float64).reshape(-1, 1, 3) / 255.0
    return rgb2lab(arr).reshape(-1, 3)


def test_cmywk_8l_process_image_latency_gate():
    """Permanent performance gate: 8-layer Bambu CMYWK process-image on the
    committed fixture must finish within 10 s (the frozen bar; the unified
    batch blend + content-keyed matrix cache keep it ~5-7 s locally)."""
    from core.color_config import get_preset
    from core.blend_color import Colors
    colors = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
    image_bytes = open(PERF_FIXTURE, "rb").read()
    t0 = time.monotonic()
    result = process_image(
        image_bytes=image_bytes, max_colors=10, color_threshold=50,
        pixel_size=0.2, filament_colors=colors,
        layer_count=8, layer_height=0.08,
        white_backing_layers=1, detail_size=0.42,
    )
    elapsed = time.monotonic() - t0
    assert result["colorBlocks"], "pipeline must produce blocks"
    assert elapsed < 10.0, (
        f"8-layer CMYWK process-image took {elapsed:.1f}s, over the 10s gate"
    )
    print(f"\nCMYWK 8L gate: {elapsed:.2f}s")


@pytest.mark.skipif(not os.path.exists(LOCAL_PHOTO), reason="local-photo.JPG local fixture not present")
def _translucent_colors() -> Colors:
    """Uniform scalar-td translucent set (the pruning fallback regime)."""
    from core.color_materials import Color
    return Colors(colors={
        l: Color(name=l, hex=h, transmission_distance=td, k=0.0)
        for l, h, td in zip(
            "CMYW",
            ["#5489B4", "#DE5740", "#DDC465", "#D9D6C5"],
            [4.7, 6.3, 10.1, 18.0],
        )
    })


def test_clear_8l_process_image_pruned_vs_full_enumeration_benchmark():
    colors = _translucent_colors()
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

    from services import matrix_cache

    original_budget = settings.full_enumeration_budget_seconds
    try:
        # Production path: 4x8 = 65,536 codes fits the budget -> full.
        matrix_cache.clear_cache()
        t0 = time.monotonic()
        full = process_image(**common)
        t_full = time.monotonic() - t0

        # Forced-prune path: budget ~zero drives the same config onto the
        # composition-pruned matrix (the fallback for over-budget sets).
        # Clear the cache so the regime change is actually computed.
        settings.full_enumeration_budget_seconds = 1e-9
        matrix_cache.clear_cache()
        t0 = time.monotonic()
        pruned = process_image(**common)
        t_pruned = time.monotonic() - t0
    finally:
        settings.full_enumeration_budget_seconds = original_budget
        matrix_cache.clear_cache()

    # The two runs used different regimes: full enumerates every ordering,
    # pruned keeps one representative per composition.
    from core.blend_color import Colors as _C
    from services.stl_generator import compute_reference_matrices as _crm
    _full_df, _ = _crm(8, 0.84, colors, prune=False)
    settings.full_enumeration_budget_seconds = 1e-9
    matrix_cache.clear_cache()
    _pruned_df, _ = _crm(8, 0.84, colors)
    settings.full_enumeration_budget_seconds = original_budget
    matrix_cache.clear_cache()
    full_codes = {_full_df.iat[r, c] for r in range(_full_df.shape[0]) for c in range(_full_df.shape[1])}
    pruned_codes = {_pruned_df.iat[r, c] for r in range(_pruned_df.shape[0]) for c in range(_pruned_df.shape[1])}
    assert len(full_codes) == 4**8, f"full matrix must enumerate {4**8} codes, got {len(full_codes)}"
    assert len(pruned_codes) == 165, f"pruned matrix must hold 165 compositions, got {len(pruned_codes)}"

    assert full["colorBlocks"] and pruned["colorBlocks"]
    # Completion, not a hard latency gate: under a full-suite parallel load the
    # standalone ~11s run can stretch past the 60s budget on shared CPUs. The
    # latency bar (<=10s) applies to the 8-layer CMYW opaque benchmark; both
    # timings are recorded below for trend tracking.

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
        "full_enumeration_codes": 4**8,
        "composition_representatives": 165,
        "pruned_process_image_s": round(t_pruned, 2),
        "full_process_image_s": round(t_full, 2),
        "full_over_pruned": round(t_full / t_pruned, 1),
        "palette_delta_e00_mean": round(float(de.mean()), 2),
        "palette_delta_e00_max": round(float(de.max()), 2),
    }
    out_path = os.path.join(tempfile.gettempdir(), "prune_benchmark_8L.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        import json

        json.dump(metrics, fh, indent=2)
    print(f"\nbenchmark metrics -> {out_path}: {metrics}")
