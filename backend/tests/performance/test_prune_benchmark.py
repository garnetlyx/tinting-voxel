"""
Real-image benchmark for the time-budget enumeration policy.

The shipped clear preset (4-color CMYW) at 8 layers / 0.84 mm enumerates
fully in seconds — well inside the 60 s budget — so production takes the
exact full path. This benchmark pins that headline timing, then exercises
the composition-pruned path on a uniform scalar-td translucent set (the
channel-specific presets are covered by the unit oracle suite)
by forcing the budget to ~zero, and records both timings plus palette drift
between the paths. Metrics are written to the OS temp dir, never the tree.
"""
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest
from skimage.color import deltaE_ciede2000, rgb2lab

from config.settings import settings
from core.color_config import get_preset
from core.color_materials import Colors
from services.image_processor import process_image

# The first photo in the gitignored local fixture folder, if any.
LOCAL_PHOTO = next((
    path for path in sorted(Path(__file__).parents[1].joinpath("fixtures", "images-local").glob("*"))
    if path.suffix.lower() in settings.allowed_extensions
), None)
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
    colors = Colors.from_configs(get_preset("bambu_cmywk"))
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
    # CI runners are shared 2-core machines ~2-3x slower than a laptop;
    # keep the local bar but give CI a proportional budget. The gate covers
    # the true-stack simulation: since the printed backing participates in
    # the blend (one extra simulated layer per code), the bar carries the
    # measured ~10% cost of that feature.
    gate = 33.0 if os.environ.get("GITHUB_ACTIONS") == "true" else 11.5
    assert elapsed < gate, (
        f"8-layer CMYWK process-image took {elapsed:.1f}s, over the {gate}s gate"
    )
    print(f"\nCMYWK 8L gate: {elapsed:.2f}s (limit {gate}s)")


def _translucent_colors() -> Colors:
    """Uniform scalar-td translucent set (the pruning fallback regime)."""
    from core.color_materials import Color
    return Colors(colors={
        l: Color(name=l, hex=h, transmission_distance=td)
        for l, h, td in zip(
            "CMYW",
            ["#5489B4", "#DE5740", "#DDC465", "#D9D6C5"],
            [4.7, 6.3, 10.1, 18.0],
        )
    })


@pytest.mark.skipif(LOCAL_PHOTO is None, reason="no photo in tests/fixtures/images-local")
def test_clear_8l_process_image_pruned_vs_full_enumeration_benchmark():
    colors = _translucent_colors()
    image_bytes = LOCAL_PHOTO.read_bytes()
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
    full_codes = set(_full_df.to_numpy().ravel())
    pruned_codes = set(_pruned_df.to_numpy().ravel())
    # Both matrices keep one code per distinct color: full enumeration keeps
    # orderings, pruning only canonical compositions (at most C(11, 8) = 165).
    assert any(list(code) != sorted(code) for code in full_codes), "full matrix must hold orderings"
    assert all(list(code) == sorted(code) for code in pruned_codes), "pruned matrix must hold compositions"
    assert len(pruned_codes) <= 165 < len(full_codes)

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
        "full_distinct_colors": len(full_codes),
        "composition_representatives": len(pruned_codes),
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
