#!/usr/bin/env python3
"""Independent forward-alignment check (no pytest): the app's blend model,
fed the paper presets, versus the frozen research prediction CSVs.

Run from backend/:
    .venv/bin/python tests/fixtures/paper_alignment/verify_alignment.py

Prints max|dRGB| per benchmark; exits non-zero if any exceeds its bound.
See README.md in this directory for fixture provenance.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.blend_color import BlendTestGenerator, Colors  # noqa: E402
from core.color_config import ColorConfig, get_preset  # noqa: E402

HERE = Path(__file__).resolve().parent


def load_cells(name):
    with open(HERE / f"{name}.csv", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [
        (r["code"], np.array([float(r["pred_R"]), float(r["pred_G"]), float(r["pred_B"])]))
        for r in rows
    ]


def randmix5_colors():
    materials = json.load(open(HERE / "randmix5_materials.json", encoding="utf-8"))
    return Colors.from_configs([
        ColorConfig(name=m["name"], hex=m["hex"],
                    transmission_distance=m["transmission_distance"], k=m["k"])
        for m in materials
    ])


BENCHMARKS = [
    ("plate06_a_standard", lambda: Colors.from_configs(get_preset("bambu_cmywk_phase6")), 0.32, 0.011),
    ("randmix5_a_beige_safe", randmix5_colors, 0.32, 0.011),
    ("clear_cmyg_p07_def", lambda: Colors.from_configs(get_preset("clear_cmyg")), 0.84, 1e-6),
    ("clear_cmyw_p08_kxa", lambda: Colors.from_configs(get_preset("clear_cmyw")), 0.84, 1e-6),
]


def main() -> int:
    failures = 0
    for name, colors_fn, layer_height, bound in BENCHMARKS:
        cells = load_cells(name)
        gen = BlendTestGenerator(colors=colors_fn(), layer_height=layer_height,
                                 layer_count_max=4, verbose=False)
        max_diff, worst = 0.0, None
        for code, reference in cells:
            predicted = np.asarray(gen.code_to_rgb(code), dtype=np.float64)
            diff = float(np.abs(predicted - reference).max())
            if diff > max_diff:
                max_diff, worst = diff, code
        status = "OK " if max_diff <= bound else "FAIL"
        print(f"{status} {name}: max|dRGB|={max_diff:.6f} at {worst!r} (bound {bound})")
        if max_diff > bound:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
