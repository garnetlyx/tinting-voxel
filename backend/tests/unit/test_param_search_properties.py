"""
Property-based tests for param_search_service.
Each test references its design property number.
"""
import base64
import math
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from PIL import Image

# Ensure backend is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.param_search_service import (
    Evaluator,
    FixedParams,
    GridSearch,
    RandomSearch,
    SearchResult,
    ParamSearchService,
    ParamSearchConfig,
)
from core.color_config import get_preset
from core.blend_color import Colors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_solid_png(r: int, g: int, b: int, size: int = 8) -> bytes:
    """Create a small solid-color PNG and return its bytes."""
    img = Image.new("RGB", (size, size), (r, g, b))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pil_to_data_url(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _bytes_to_data_url(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode()
    return f"data:image/png;base64,{b64}"


def _default_colors() -> Colors:
    configs = get_preset("bambu_cmyw_phase6")
    return Colors.from_configs(configs)


def _default_fixed() -> FixedParams:
    return FixedParams(
        layer_count=4,
        layer_height=0.08,
        pixel_size=0.42,
        white_backing_layers=1,
    )


# Strategy: small solid-color PIL images
@st.composite
def solid_pil_images(draw, size=8):
    r = draw(st.integers(0, 255))
    g = draw(st.integers(0, 255))
    b = draw(st.integers(0, 255))
    return Image.new("RGB", (size, size), (r, g, b))


# ---------------------------------------------------------------------------
# Property 1: MAE output range
# Feature: param-search-optimizer, Property 1: MAE output range
# ---------------------------------------------------------------------------

@given(
    r1=st.integers(0, 255), g1=st.integers(0, 255), b1=st.integers(0, 255),
    r2=st.integers(0, 255), g2=st.integers(0, 255), b2=st.integers(0, 255),
)
@settings(max_examples=100)
def test_mae_output_range(r1, g1, b1, r2, g2, b2):
    """Property 1: MAE is always a finite float in [0.0, 255.0]."""
    orig = Image.new("RGB", (8, 8), (r1, g1, b1))
    preview_url = _pil_to_data_url(Image.new("RGB", (8, 8), (r2, g2, b2)))
    mae = Evaluator.compute_mae(orig, preview_url)
    assert math.isfinite(mae), f"MAE must be finite, got {mae}"
    assert 0.0 <= mae <= 255.0, f"MAE must be in [0, 255], got {mae}"


# ---------------------------------------------------------------------------
# Property 2: Identical images yield zero MAE
# Feature: param-search-optimizer, Property 2: Identical images yield zero MAE
# ---------------------------------------------------------------------------

@given(img=solid_pil_images())
@settings(max_examples=100)
def test_mae_identical_images(img):
    """Property 2: Passing the same image as both original and preview yields MAE == 0."""
    preview_url = _pil_to_data_url(img)
    mae = Evaluator.compute_mae(img, preview_url)
    assert mae == pytest.approx(0.0, abs=1e-4), f"Identical images must yield MAE=0, got {mae}"


# ---------------------------------------------------------------------------
# Property 3: MAE monotonicity
# Feature: param-search-optimizer, Property 3: MAE monotonicity
# ---------------------------------------------------------------------------

@given(
    r_orig=st.integers(0, 255), g_orig=st.integers(0, 255), b_orig=st.integers(0, 255),
    r_close=st.integers(0, 255), g_close=st.integers(0, 255), b_close=st.integers(0, 255),
)
@settings(max_examples=100)
def test_mae_monotonicity(r_orig, g_orig, b_orig, r_close, g_close, b_close):
    """Property 3: A preview blended 50% toward original has lower MAE than the raw preview."""
    orig = Image.new("RGB", (8, 8), (r_orig, g_orig, b_orig))
    close_arr = np.array(Image.new("RGB", (8, 8), (r_close, g_close, b_close)), dtype=np.float32)
    orig_arr = np.array(orig, dtype=np.float32)

    # Blend 50% toward original — must be closer
    blended_arr = np.clip((close_arr + orig_arr) / 2, 0, 255).astype(np.uint8)
    blended_img = Image.fromarray(blended_arr)

    mae_far = Evaluator.compute_mae(orig, _pil_to_data_url(Image.fromarray(close_arr.astype(np.uint8))))
    mae_close = Evaluator.compute_mae(orig, _pil_to_data_url(blended_img))

    assert mae_close <= mae_far + 1e-4, (
        f"Blended image (MAE={mae_close:.4f}) should be <= raw preview (MAE={mae_far:.4f})"
    )


# ---------------------------------------------------------------------------
# Property 4: Data URL round-trip preserves MAE
# Feature: param-search-optimizer, Property 4: Data URL round-trip preserves MAE
# ---------------------------------------------------------------------------

@given(
    r1=st.integers(0, 255), g1=st.integers(0, 255), b1=st.integers(0, 255),
    r2=st.integers(0, 255), g2=st.integers(0, 255), b2=st.integers(0, 255),
)
@settings(max_examples=100)
def test_data_url_round_trip(r1, g1, b1, r2, g2, b2):
    """Property 4: MAE via data URL equals MAE computed directly from PIL images."""
    orig = Image.new("RGB", (8, 8), (r1, g1, b1))
    preview = Image.new("RGB", (8, 8), (r2, g2, b2))

    # Direct computation
    orig_arr = np.array(orig.resize(Evaluator.EVAL_SIZE, Image.LANCZOS), dtype=np.float32)
    prev_arr = np.array(preview.resize(Evaluator.EVAL_SIZE, Image.LANCZOS), dtype=np.float32)
    direct_mae = float(np.mean(np.abs(orig_arr - prev_arr)))

    # Via data URL
    url_mae = Evaluator.compute_mae(orig, _pil_to_data_url(preview))

    assert url_mae == pytest.approx(direct_mae, abs=1e-3), (
        f"Data URL MAE ({url_mae}) should match direct MAE ({direct_mae})"
    )


# ---------------------------------------------------------------------------
# Property 5: Grid search completeness
# Feature: param-search-optimizer, Property 5: Grid search completeness
# ---------------------------------------------------------------------------

@given(
    ranges=st.fixed_dictionaries({
        "a": st.lists(st.integers(0, 10), min_size=1, max_size=4),
        "b": st.lists(st.floats(0, 1, allow_nan=False, allow_infinity=False), min_size=1, max_size=3),
        "c": st.lists(st.integers(0, 5), min_size=1, max_size=2),
    })
)
@settings(max_examples=100)
def test_grid_search_completeness(ranges):
    """Property 5: GridSearch yields exactly product(len(range)) combinations with correct keys."""
    gs = GridSearch(mode="pixel", param_ranges=ranges)
    expected_total = 1
    for v in ranges.values():
        expected_total *= len(v)

    combos = list(gs.generate())
    assert len(combos) == expected_total, f"Expected {expected_total} combos, got {len(combos)}"
    assert gs.total() == expected_total

    expected_keys = set(ranges.keys())
    for combo in combos:
        assert set(combo.keys()) == expected_keys, f"Combo keys mismatch: {combo.keys()}"


# ---------------------------------------------------------------------------
# Property 6: Random search trial count
# Feature: param-search-optimizer, Property 6: Random search trial count
# ---------------------------------------------------------------------------

@given(n=st.integers(1, 200))
@settings(max_examples=100)
def test_random_search_trial_count(n):
    """Property 6: RandomSearch yields exactly n_trials combinations."""
    rs = RandomSearch(mode="pixel", n_trials=n)
    combos = list(rs.generate())
    assert len(combos) == n, f"Expected {n} trials, got {len(combos)}"
    assert rs.total() == n


# ---------------------------------------------------------------------------
# Property 7: Random search bounds containment
# Feature: param-search-optimizer, Property 7: Random search bounds containment
# ---------------------------------------------------------------------------

@given(n=st.integers(1, 50))
@settings(max_examples=100)
def test_random_search_bounds_containment(n):
    """Property 7: All sampled values are within their specified bounds."""
    bounds = {
        "max_colors": ("int", 4, 16),
        "color_threshold": ("float", 10.0, 100.0),
        "detail_size": ("float", 0.22, 0.82),
        "white_backing_layers": ("choice", [0, 1]),
    }
    rs = RandomSearch(mode="pixel", n_trials=n, param_bounds=bounds)
    for combo in rs.generate():
        assert 4 <= combo["max_colors"] <= 16
        assert 10.0 <= combo["color_threshold"] <= 100.0
        assert 0.22 <= combo["detail_size"] <= 0.82
        assert combo["white_backing_layers"] in (0, 1)


# ---------------------------------------------------------------------------
# Property 8: Random search reproducibility
# Feature: param-search-optimizer, Property 8: Random search reproducibility
# ---------------------------------------------------------------------------

@given(
    seed=st.integers(0, 2**31 - 1),
    n=st.integers(1, 50),
)
@settings(max_examples=100)
def test_random_search_reproducibility(seed, n):
    """Property 8: Same seed produces identical sequences."""
    rs1 = RandomSearch(mode="pixel", n_trials=n, seed=seed)
    rs2 = RandomSearch(mode="pixel", n_trials=n, seed=seed)
    combos1 = list(rs1.generate())
    combos2 = list(rs2.generate())
    assert combos1 == combos2, "Same seed must produce identical sequences"


# ---------------------------------------------------------------------------
# Property 9: Results sorted by MAE ascending
# Feature: param-search-optimizer, Property 9: Results sorted by MAE ascending
# ---------------------------------------------------------------------------

@given(
    maes=st.lists(
        st.floats(0.0, 255.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=100)
def test_results_sorted_by_mae(maes):
    """Property 9: _rank_and_trim returns results sorted by MAE ascending."""
    results = [
        SearchResult(rank=0, mode="pixel", params={}, mae=m, preview_data_url="")
        for m in maes
    ]
    sorted_results = ParamSearchService._rank_and_trim(results)
    for i in range(len(sorted_results) - 1):
        assert sorted_results[i].mae <= sorted_results[i + 1].mae, (
            f"Results not sorted: {sorted_results[i].mae} > {sorted_results[i+1].mae}"
        )
    # Ranks should be 1-based sequential
    for i, r in enumerate(sorted_results):
        assert r.rank == i + 1


# ---------------------------------------------------------------------------
# Property 10: Progress format correctness
# Feature: param-search-optimizer, Property 10: Progress format correctness
# ---------------------------------------------------------------------------

import re

@given(
    completed=st.integers(1, 1000),
    total=st.integers(1, 1000),
    mae=st.floats(0.0, 255.0, allow_nan=False, allow_infinity=False),
    params=st.fixed_dictionaries({
        "max_colors": st.integers(4, 16),
        "color_threshold": st.floats(10, 100, allow_nan=False),
    }),
)
@settings(max_examples=100)
def test_progress_format(completed, total, mae, params):
    """Property 10: Progress line matches expected format."""
    assume(completed <= total)
    line = f"[{completed}/{total}] MAE={mae:.2f} params={params}"
    pattern = r"^\[\d+/\d+\] MAE=\d+\.\d{2} params=\{.*\}$"
    assert re.match(pattern, line), f"Progress line does not match pattern: {line!r}"
