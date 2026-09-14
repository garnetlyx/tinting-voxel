"""Forward alignment with the paper (IJAMT latest) — the app's unified blend
model, fed the paper presets, must reproduce the research engine's per-cell
predictions for the four paper benchmarks:

- PLATE-06-H2C-A (bambu CMYWK, A-standard fitted coefficients, lh 0.32 mm)
- RANDMIX5-H2C-A (five arbitrary filaments, beige-safe fitted coefficients)
- Clear CMYG plate print 1, default config (P07-def staircase td_rgb, lh 0.84)
- Clear CMYW PLATE-08-KX-A (P08-kxa staircase td_rgb, lh 0.84)

Reference data: tests/fixtures/paper_alignment/ (frozen research outputs;
see that directory's README for provenance).
"""
import csv
import json
from pathlib import Path

import numpy as np
import pytest

from core.blend_color import BlendTestGenerator, Colors
from core.color_config import ColorConfig, get_preset

FIXTURES = Path(__file__).parents[1] / "fixtures" / "paper_alignment"


def _load_cells(name: str) -> list[tuple[str, np.ndarray]]:
    with open(FIXTURES / f"{name}.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [
        (r["code"], np.array([float(r["pred_R"]), float(r["pred_G"]), float(r["pred_B"])]))
        for r in rows
    ]


def _randmix5_colors() -> Colors:
    materials = json.load(open(FIXTURES / "randmix5_materials.json", encoding="utf-8"))
    return Colors.from_configs([
        ColorConfig(
            name=m["name"],
            hex=m["hex"],
            transmission_distance=m["transmission_distance"],
            k=m["k"],
        )
        for m in materials
    ])


# (fixture, colors, layer_height, tolerance)
# plate-06 / randmix5 CSVs inherit the research reports' 2-dp rounding, so
# the bound is the rounding half-step; the clear CSVs are full-precision
# engine outputs, so the bound is float-tight.
BENCHMARKS = [
    pytest.param(
        "plate06_a_standard",
        lambda: Colors.from_configs(get_preset("bambu_cmywk_phase6")),
        0.32, 0.011, id="plate06_a_standard",
    ),
    pytest.param(
        "randmix5_a_beige_safe",
        _randmix5_colors,
        0.32, 0.011, id="randmix5_a_beige_safe",
    ),
    pytest.param(
        "clear_cmyg_p07_def",
        lambda: Colors.from_configs(get_preset("clear_cmyg")),
        0.84, 1e-6, id="clear_cmyg_p07_def",
    ),
    pytest.param(
        "clear_cmyw_p08_kxa",
        lambda: Colors.from_configs(get_preset("clear_cmyw")),
        0.84, 1e-6, id="clear_cmyw_p08_kxa",
    ),
]


@pytest.mark.parametrize("fixture,colors_fn,layer_height,tol", BENCHMARKS)
def test_forward_alignment_with_paper(fixture, colors_fn, layer_height, tol):
    """App predictions match the research engine's per-cell predictions."""
    cells = _load_cells(fixture)
    assert cells, f"fixture {fixture} is empty"

    colors = colors_fn()
    gen = BlendTestGenerator(
        colors=colors, layer_height=layer_height, layer_count_max=4, verbose=False,
    )

    max_diff = 0.0
    worst = None
    for code, reference in cells:
        predicted = np.asarray(gen.code_to_rgb(code), dtype=np.float64)
        diff = float(np.abs(predicted - reference).max())
        if diff > max_diff:
            max_diff, worst = diff, code

    assert max_diff <= tol, (
        f"{fixture}: app model deviates from the paper predictions by "
        f"max|dRGB|={max_diff:.4f} at code {worst!r} (tolerance {tol})"
    )
