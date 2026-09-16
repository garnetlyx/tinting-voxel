"""Forced-W allocation: near-white regions must print as real white stacks.

Physical rationale: an empty/thin-CMY region over white backing only LOOKS
white in the model (perfect backing assumption); the printed result depends
on the backing surface shining through and deviates from the prediction.
Near-white targets therefore map to W-dominant codes (>= half the layers
are the white filament) via Color.map_to_nearest_color's white_labels rule.
"""
from pathlib import Path

import numpy as np
import pytest

from core.blend_color import Colors
from core.color_config import get_preset
from core.color_materials import Color
from services.stl_generator import compute_reference_matrices

LOCAL_PHOTO = Path(__file__).parents[2] / "tests/fixtures/images-local/local-photo.JPG"


def _w_fraction(code: str, white_labels: set) -> float:
    if not code:
        return 0.0
    return sum(1 for ch in code if ch in white_labels) / len(code)


def test_white_labels_resolution():
    colors = Colors.from_configs(get_preset("bambu_cmyw_phase6"))
    assert colors.white_labels() == {"W"}  # pure #FFFFFF filament
    clear = Colors.from_configs(get_preset("clear_cmyg"))
    assert clear.white_labels() == set()
    clear_w = Colors.from_configs(get_preset("clear_cmyw"))
    assert clear_w.white_labels() == set()  # tinted #D9D6C5 "white"
    from core.color_config import ColorConfig
    from tests.unit.test_paper_alignment import _randmix_colors
    assert _randmix_colors().white_labels() == set()  # beige W does not trigger


def test_near_white_target_maps_to_w_dominant_code():
    colors = Colors.from_configs(get_preset("bambu_cmyw_phase6"))
    white_labels = colors.white_labels()
    code_df, rgb_df = compute_reference_matrices(8, 0.32, colors, n_targets=4)

    codes, _rgbs = Color.map_to_nearest_color(
        [(250, 250, 250), (243, 244, 240)], code_df, rgb_df,
        white_labels=white_labels,
    )
    for code in codes:
        assert _w_fraction(code, white_labels) >= 0.5, (
            f"near-white target must map to a W-dominant code, got {code}"
        )

    # Chromatic targets are unaffected by the rule.
    codes, _ = Color.map_to_nearest_color(
        [(30, 30, 140), (180, 40, 40)], code_df, rgb_df,
        white_labels=white_labels,
    )
    for code in codes:
        assert _w_fraction(code, white_labels) < 0.5, (
            f"chromatic target should not be forced to white stacks, got {code}"
        )


@pytest.mark.skipif(not LOCAL_PHOTO.exists(), reason="local-photo.JPG local fixture not present")
def test_local-photo_white_region_cells_are_w_dominant():
    """Sample the actual white-cotton pixels of the local-photo photo and verify
    each sampled cell maps to a W-dominant stack under the canonical Bambu
    CMYW config."""
    from PIL import Image

    img = np.asarray(Image.open(LOCAL_PHOTO).convert("RGB"), dtype=float)
    lum = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114) / 255.0
    ys, xs = np.where(lum >= 0.92)
    assert len(xs) > 100, "local-photo fixture must contain white regions"
    idx = np.linspace(0, len(xs) - 1, 64).round().astype(int)
    sampled = [tuple(int(v) for v in img[ys[i], xs[i]]) for i in idx]

    colors = Colors.from_configs(get_preset("bambu_cmyw_phase6"))
    white_labels = colors.white_labels()
    code_df, rgb_df = compute_reference_matrices(8, 0.32, colors, n_targets=len(sampled))
    codes, _ = Color.map_to_nearest_color(sampled, code_df, rgb_df, white_labels=white_labels)

    dominant = [c for c in codes if _w_fraction(c, white_labels) >= 0.5]
    assert len(dominant) == len(codes), (
        f"{len(codes) - len(dominant)}/{len(codes)} sampled white-region cells "
        f"are not W-dominant: {sorted(set(codes))}"
    )


@pytest.mark.skipif(not LOCAL_PHOTO.exists(), reason="local-photo.JPG local fixture not present")
def test_local-photo_process_pixel_labels_and_param_search_gate():
    """Process-level, two frozen gates on the REAL pipeline:

    1. Pixel labels: build the per-pixel label map from colorBlocks and
       check the assigned code at ACTUAL sampled white-cotton coordinates
       (not nearest-palette inference) — every sampled white-region pixel
       must carry a W-dominant code, and no palette entry may be empty.
    2. Param-search engine: run the same ParamSearchService that powers
       /api/param-search (grid strategy) and require top-1 MAE <= 76
       (>= 40% better than the 127.86 baseline).
    """
    from services.image_processor import process_image
    from services.param_search_service import (
        FixedParams, ParamSearchConfig, ParamSearchService,
    )
    from PIL import Image

    colors = Colors.from_configs(get_preset("bambu_cmyw_phase6"))
    white_labels = colors.white_labels()
    result = process_image(
        image_bytes=LOCAL_PHOTO.read_bytes(),
        max_colors=14, color_threshold=11.25, pixel_size=0.42,
        filament_colors=colors, layer_count=8, layer_height=0.32,
        white_backing_layers=1, detail_size=0.33,
    )
    blocks = result["colorBlocks"]
    codes = [m["code"] for m in result["mappedBlockColors"]]
    assert codes and all(codes), "output must contain no empty palette codes"

    dims = result["imageDimensions"]
    label = {}
    for i, block in enumerate(blocks):
        for p in block["pixels"]:
            label[(p["x"], p["y"])] = i

    img = np.asarray(Image.open(LOCAL_PHOTO).convert("RGB"), dtype=float)
    # The pixel grid runs at the processed resolution; local-photo maps 1:1.
    scale_x = dims["width"] / img.shape[1]
    scale_y = dims["height"] / img.shape[0]
    lum = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114) / 255.0
    ys, xs = np.where(lum >= 0.92)
    assert len(xs) > 100, "local-photo fixture must contain white regions"
    idx = np.linspace(0, len(xs) - 1, 64).round().astype(int)
    for i in idx:
        gx, gy = int(xs[i] * scale_x), int(ys[i] * scale_y)
        block_idx = label.get((gx, gy))
        assert block_idx is not None, f"white pixel ({gx},{gy}) has no label"
        code = codes[block_idx]
        assert _w_fraction(code, white_labels) >= 0.5, (
            f"white-region pixel ({gx},{gy}) carries non-W-dominant code {code}"
        )

    config = ParamSearchConfig(
        mode="pixel", strategy="grid", n_trials=6, seed=7,
        fixed=FixedParams(
            layer_height=0.32, layer_count=8,
            white_backing_layers=1, pixel_size=0.42,
        ),
        colors=colors, param_ranges=None, top_n=5,
    )
    results = ParamSearchService(config).run(LOCAL_PHOTO.read_bytes())
    assert results, "param search must return candidates"
    top1 = min(r.mae for r in results)
    assert top1 <= 76.0, f"param-search top-1 MAE {top1:.2f} over the 76 gate"
