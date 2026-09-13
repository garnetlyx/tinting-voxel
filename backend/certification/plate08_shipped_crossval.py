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
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from skimage.color import deltaE_ciede2000, rgb2lab

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(BACKEND_ROOT)  # the git worktree root
RESEARCH = "/Users/gl/Dropbox/mine/projects/research/tinting-voxel-research"
sys.path.insert(0, os.path.join(RESEARCH, "scripts"))
sys.path.insert(0, RESEARCH)

from clear_plate_crossval import apply_orientation, de_mean, load_code_grid, sample_cells  # noqa: E402
from calibration.core.photo_preprocessor import PhotoPreprocessor  # noqa: E402

LN10 = float(np.log(10.0))
LAYER_MM = 0.84
# Registered capture geometry (research crossval report + SCF Table S7):
# the black-backing photo was shot 180° rotated relative to white.
ORIENTATIONS = {"w": "rot0", "b": "rot180"}

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
    ) % BACKEND_ROOT
    out = _sp.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    colors = json.loads(out)
    labels = ["C", "M", "Y", "W"]
    return {labels[i]: (c["hex"], c["td"], c["k"]) for i, c in enumerate(colors)}


def _engine_pin_ok() -> bool:
    """The ENGINE submodule (the blend math used for conventions) must be
    pinned at 165fa55; the research repo itself moves independently."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=os.path.join(RESEARCH, "engine"),
            capture_output=True, text=True,
        ).stdout.strip()
        return out == "165fa55cba8e0a6fc6b6b2e1ab69cdf9d139f287"
    except Exception:
        return False


def main(check_only: bool = False):
    if not _engine_pin_ok():
        print("research engine pin drifted from 165fa55 — certification invalid")
        sys.exit(1)
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
            "orientations": ORIENTATIONS,
            "layer_mm": LAYER_MM,
        },
        "command": "cd backend && .venv/bin/python certification/plate08_shipped_crossval.py",
        "check_command": "cd backend && .venv/bin/python certification/plate08_shipped_crossval.py --check",
        "research_engine_pin": "165fa55cba8e0a6fc6b6b2e1ab69cdf9d139f287",
        # Non-circular provenance: the tree hash of the commit that last
        # touched backend/core/color_config.py (the certified values), NOT
        # the working HEAD — reruns from any branch check the same source.
        "certified_values_source": {
            "app_commit": subprocess.run(
                ["git", "log", "-1", "--format=%H", "--", "backend/core/color_config.py"],
                cwd=REPO_ROOT, capture_output=True, text=True,
            ).stdout.strip(),
            "color_config_blob_sha1": subprocess.run(
                ["git", "rev-parse", "HEAD:backend/core/color_config.py"],
                cwd=REPO_ROOT, capture_output=True, text=True,
            ).stdout.strip(),
            "color_config_sha256": hashlib.sha256(
                open(os.path.join(BACKEND_ROOT, "core", "color_config.py"), "rb").read()
            ).hexdigest(),
        },
        "backings": {},
    }

    pp = PhotoPreprocessor(grid_size=16)
    for bk, bg in {"w": (255.0, 255.0, 255.0), "b": (20.0, 20.0, 20.0)}.items():
        res = pp.process(PHOTOS[bk])
        warped = os.path.join("/tmp", f"plate08_warp_{bk}.png")  # noqa: /tmp only
        Image.fromarray(res.image).save(warped)
        meas = sample_cells(warped)
        os.remove(warped)
        meas_o = apply_orientation(meas, ORIENTATIONS[bk])
        pred = predict_grid(code_grid, np.array(bg) / 255.0, shipped)
        shipped_score = round(de_mean(pred, meas_o), 2)
        ref_spec = {ch: (kxa_reference[ch]["hex"], kxa_reference[ch]["td"], 0.0) for ch in kxa_reference}
        ref_pred = predict_grid(code_grid, np.array(bg) / 255.0, ref_spec)
        ref_score = round(de_mean(ref_pred, meas_o), 2)
        report["backings"][bk] = {"shipped_preset": shipped_score, "same_batch_reference": ref_score}
        print(f"PLATE-08-KX-A {bk}: shipped {shipped_score:.2f} | same-batch ref {ref_score:.2f}")

    out_dir = "/tmp" if check_only else os.path.join(BACKEND_ROOT, "certification")
    out = os.path.join(out_dir, "plate08_shipped_crossval.json")
    if check_only:
        tracked = os.path.join(BACKEND_ROOT, "certification", "plate08_shipped_crossval.json")
        existing = json.load(open(tracked))
        # Every provenance/input field must match, not just the scores:
        # formula, inputs (hashes, orientation, layer), both preset tables,
        # and the certified source revision. app_commit inside
        # certified_values_source is HEAD-relative at certification time and
        # re-derives per run, so compare its tree hash (immutable).
        compare_keys = [k for k in report if k != "certified_values_source"]
        drift = {
            k: (existing.get(k), report.get(k))
            for k in compare_keys
            if existing.get(k) != report.get(k)
        }
        src_key = "certified_values_source"
        for field in ("app_commit", "color_config_blob_sha1", "color_config_sha256"):
            a = (existing.get(src_key) or {}).get(field)
            b = (report.get(src_key) or {}).get(field)
            if a != b:
                drift[f"{src_key}.{field}"] = (a, b)
        if not (report.get(src_key) or {}).get("app_commit"):
            drift[f"{src_key}.app_commit"] = ("missing", "(empty)")
        if drift:
            print("CERTIFICATION DRIFT DETECTED:")
            print(json.dumps(drift, indent=2)[:2000])
            sys.exit(1)
        print(f"check passed (identical to {tracked}); report also written to {out}")
    json.dump(report, open(out, "w"), indent=2)
    if not check_only:
        print(f"report -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="read-only verification against the tracked report; writes only to /tmp")
    args = ap.parse_args()
    main(check_only=args.check)
