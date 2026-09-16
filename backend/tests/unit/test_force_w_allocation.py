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
def test_local-photo_process_image_white_cluster_w_dominant_and_mae_gate():
    """Process-level: run the REAL pipeline on local-photo with the canonical
    Bambu CMYW config. The cluster covering sampled white-cotton pixels
    must carry a W-dominant code (no empty codes anywhere), and the
    fixed-config weighted MAE must stay under the frozen 76 gate (the
    param-search baseline candidate always includes this configuration,
    so top-1 MAE <= this value)."""
    from services.image_processor import process_image

    colors = Colors.from_configs(get_preset("bambu_cmyw_phase6"))
    white_labels = colors.white_labels()
    result = process_image(
        image_bytes=LOCAL_PHOTO.read_bytes(),
        max_colors=14, color_threshold=11.25, pixel_size=0.42,
        filament_colors=colors, layer_count=8, layer_height=0.32,
        white_backing_layers=1, detail_size=0.33,
    )
    palette = result["mappedBlendPalette"]
    codes = [e["code"] for e in palette]
    assert codes and all(codes), "output must contain no empty palette codes"

    # White-region coverage: sampled bright pixels resolve to a W-dominant
    # cluster code through the pipeline's own palette.
    from PIL import Image

    img = np.asarray(Image.open(LOCAL_PHOTO).convert("RGB"), dtype=float)
    lum = (img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114) / 255.0
    ys, xs = np.where(lum >= 0.92)
    idx = np.linspace(0, len(xs) - 1, 64).round().astype(int)
    sampled = np.array([img[ys[i], xs[i]] for i in idx])

    src = np.array([e["sourceRgb"] for e in palette], dtype=float)
    code_of = {tuple(e["sourceRgb"]): e["code"] for e in palette}
    nearest = ((sampled[:, None, :] - src[None, :, :]) ** 2).sum(2).argmin(1)
    for i in nearest:
        code = code_of[tuple(src[i])]
        assert _w_fraction(code, white_labels) >= 0.5, (
            f"white-region cluster code {code} is not W-dominant"
        )

    # Frozen MAE gate (param-search top-1 cannot exceed the baseline).
    errs = np.array([
        np.abs(np.array(e["rgb"], float) - np.array(e["sourceRgb"], float)).mean()
        for e in palette
    ])
    weights = np.array([e["pixelCount"] for e in palette], float)
    mae = (errs * weights).sum() / weights.sum()
    assert mae <= 76.0, f"fixed-config local-photo MAE {mae:.2f} over the 76 gate"
