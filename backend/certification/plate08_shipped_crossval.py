#!/usr/bin/env python3
"""PLATE-08-KX-A cross-validation of the EXACT shipped clear_cmyw preset.

Read-only against the research repo (photos + code grid + pinned engine
geometry conventions); every output goes to this directory. Predictions use
the app's unified formula directly:

    mu_ch = ln(10)/td + k*A_ch      (k = 0 for the clear preset)
    stack color via light-loss allocation (paper Eqs. 4-8)

Usage:
    cd backend && .venv/bin/python certification/plate08_shipped_crossval.py
"""
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH = "/Users/gl/Dropbox/mine/projects/research/tinting-voxel-research"
sys.path.insert(0, os.path.join(RESEARCH, "scripts"))
sys.path.insert(0, RESEARCH)

from clear_plate_crossval import apply_orientation, de_mean, load_code_grid, sample_cells  # noqa: E402
from calibration.core.photo_preprocessor import PhotoPreprocessor  # noqa: E402

LN10 = float(np.log(10.0))
LAYER_MM = 0.84
ORIENTATION = "rot0"

CODE_CSV = os.path.join(
    RESEARCH,
    "calibration/plates/clear_cmyw/CMYW_208x208x3.36/CMYW_208x208x3.36_code.csv",
)
PHOTOS = {
    "w": os.path.join(RESEARCH, "data/photos/PLATE-08-KX-A_white_01_cross.JPG"),
    "b": os.path.join(RESEARCH, "data/photos/PLATE-08-KX-A_black_01_cross.JPG"),
}


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load_shipped_preset():
    """Read the app preset in a subprocess so the research repo's pinned
    engine `core` modules cannot shadow it (they collide by name)."""
    import subprocess as _sp
    code = (
        "import json,sys;"
        "sys.path.insert(0, %r);"
        "from core.color_config import get_preset;"
        "p = get_preset('clear_cmyw');"
        "print(json.dumps([{ 'hex': c.hex, 'td': c.transmission_distance, 'k': c.k } for c in p]))"
    ) % REPO_ROOT
    out = _sp.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    colors = json.loads(out)
    labels = ["C", "M", "Y", "W"]
    return {labels[i]: (c["hex"], c["td"], c["k"]) for i, c in enumerate(colors)}


def main():
    shipped = load_shipped_preset()
    abs_table = {}
    for ch, (hexv, td, k) in shipped.items():
        h = hexv.lstrip("#")
        rgb = tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
        abs_table[ch] = (np.array([255 - c for c in rgb]) / 255.0, td, k)

    def predict_grid(code_grid, bg, spec):
        table = {}
        for ch, (hexv, td, k) in spec.items():
            h = hexv.lstrip("#")
            rgbv = tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
            table[ch] = (np.array([255 - c for c in rgbv]) / 255.0, td, k)
        n = len(code_grid)
        out = np.zeros((n, n, 3))
        for r in range(n):
            for c in range(n):
                code = code_grid[r][c]
                transmissions = [
                    np.exp(-(LN10 / table[ch][1] + table[ch][2] * table[ch][0]) * LAYER_MM)
                    for ch in code
                ]
                remain = np.ones(3)
                loss = []
                for t in transmissions:
                    loss.append(remain * (1 - t))
                    remain = remain * t
                loss.append(remain)
                loss = np.array(loss)
                total = np.where(loss.sum(axis=0) > 0, loss.sum(axis=0), 1.0)
                loss /= total
                bw = loss[-1]
                rgb = np.ones(3)
                for i, ch in enumerate(code):
                    rgb -= table[ch][0] * loss[i]
                out[r, c] = np.clip((bw * bg + (1 - bw) * rgb) * 255, 0, 255)
        return out

    code_grid = load_code_grid(CODE_CSV)
    # Same-batch reference: staircase-KX-A thin-range per-channel means and
    # wb_corrected hexes (the research repo's own fair scalar comparator).
    # The shipped tds come from a different (profile-matched) staircase batch;
    # both are recorded so the cross-batch residual is visible.
    kxa_reference = {}
    mats = {
        "C": "ziro-light-cyan-clear",
        "M": "isanmate-light-pink",
        "Y": "sunlu-transparent-yellow",
        "W": "kingroon-transparent-pla",
    }
    for ch, mat in mats.items():
        rep = json.load(open(os.path.join(
            RESEARCH, f"data/results/staircase-KX-A/{mat}/v2/staircase_report_v2.json")))
        ft = rep["fit_thin_range"]["channels"]
        kxa_reference[ch] = {
            "hex": rep["hex"]["wb_corrected"],
            "td": round(float(np.mean([ft[c]["td"] for c in "rgb"])), 3),
            "k": 0.0,
        }

    report = {
        "sample_id": "PLATE-08-KX-A",
        "formula": "unified mu_ch = ln10/td + k*A_ch (k=0), light-loss allocation",
        "shipped_preset": {
            ch: {"hex": v[0], "td": v[1], "k": v[2]} for ch, v in shipped.items()
        },
        "same_batch_reference": kxa_reference,
        "inputs": {
            "code_grid": {"path": CODE_CSV, "sha256": sha256(CODE_CSV)},
            "photos": {
                bk: {"path": p, "sha256": sha256(p)} for bk, p in PHOTOS.items()
            },
            "orientation": ORIENTATION,
            "layer_mm": LAYER_MM,
            "engine_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
            ).stdout.strip(),
        },
        "command": "cd backend && .venv/bin/python certification/plate08_shipped_crossval.py",
        "backings": {},
    }

    pp = PhotoPreprocessor(grid_size=16)
    for bk, bg in {"w": (255.0, 255.0, 255.0), "b": (20.0, 20.0, 20.0)}.items():
        res = pp.process(PHOTOS[bk])
        warped = os.path.join(REPO_ROOT, "certification", f"_warp_{bk}.png")
        Image.fromarray(res.image).save(warped)
        meas = sample_cells(warped)
        os.remove(warped)
        meas_o = apply_orientation(meas, ORIENTATION)
        pred = predict_grid(code_grid, np.array(bg) / 255.0, shipped)
        shipped_score = round(de_mean(pred, meas_o), 2)
        ref_spec = {ch: (kxa_reference[ch]["hex"], kxa_reference[ch]["td"], 0.0) for ch in kxa_reference}
        ref_pred = predict_grid(code_grid, np.array(bg) / 255.0, ref_spec)
        ref_score = round(de_mean(ref_pred, meas_o), 2)
        report["backings"][bk] = {"shipped_preset": shipped_score, "same_batch_reference": ref_score}
        print(f"PLATE-08-KX-A {bk}: shipped {shipped_score:.2f} | same-batch ref {ref_score:.2f}")

    out = os.path.join(REPO_ROOT, "certification", "plate08_shipped_crossval.json")
    json.dump(report, open(out, "w"), indent=2)
    print("report ->", out)


if __name__ == "__main__":
    main()
