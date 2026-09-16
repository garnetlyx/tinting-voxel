"""Paper alignment: app forward model vs research-repo artifacts (IJAMT).

The app consumes calibration results only; the artifacts live in the
research repo and are read from there directly (no copies in this repo).
When the research repo is absent (CI runners), the full-artifact tests
skip and the inline golden-cell + reference-implementation cross-checks
still guard the formula.

Baselines:
- PLATE-06-H2C-A standard (bambu CMYWK, scalar form, lh 0.32 mm):
  data/results/PLATE-06-H2C-paper-matrix/runs/A-standard/per_cell_de.csv
- RANDMIX5-H2C-A beige-safe (5 arbitrary filaments, scalar form, lh 0.32):
  data/results/RANDMIX5-H2C-fit/runs/A-beige-safe/per_cell_de.csv
  materials: data/results/staircase-random5/<mat>/staircase_report_v2.json
  (hex.wb_corrected) + fitted td_reference/k/scatter_alpha/td_scale/td_gamma
- Clear CMYG P07-def / Clear CMYW P08-kxa (staircase form, lh 0.84 mm):
  calibration/plates/clear_cmyg|clear_cmyw/.../  *_code.csv + *_rgb.csv
  (full-precision engine predictions) and
  data/results/clear-plate-crossval/crossval_report.json provenance td_rgb.
"""
import csv
import json
import os
from pathlib import Path

import numpy as np
import pytest

from core.blend_color import Colors, colors_key
from core.blend_models import codes_to_rgb_batch
from core.color_config import get_preset

RESEARCH = Path(os.environ.get(
    "TINTING_RESEARCH_REPO",
    str(Path.home() / "Dropbox/mine/projects/research/tinting-voxel-research"),
)).expanduser()

requires_research = pytest.mark.skipif(
    not RESEARCH.exists(), reason=f"research repo not present: {RESEARCH}"
)

WHITE = (255, 255, 255)


def _predict(colors: Colors, codes: list, layer_height: float):
    """Batch-predict codes; codes_to_rgb_batch chunks assume uniform length,
    so group by code length first."""
    out: dict[str, tuple] = {}
    by_len: dict[int, list[str]] = {}
    for code in codes:
        by_len.setdefault(len(code), []).append(code)
    for _, group in sorted(by_len.items()):
        result = codes_to_rgb_batch(
            group, layer_height, colors_key(colors), background_rgb=WHITE
        )
        for code, rgb in zip(group, result):
            out[code] = tuple(rgb)
    return out


# ---------------------------------------------------------------------------
# Golden cells (inline paper values; run everywhere, no research repo needed)
# ---------------------------------------------------------------------------

def test_golden_cells_plate06_a_standard():
    """App preset reproduces the paper's PLATE-06-H2C-A predictions (2-dp)."""
    colors = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
    got = _predict(colors, ["CCCC", "CCCM", "CCCK"], 0.32)
    expected = [
        ("CCCC", (64.22, 127.34, 208.07)),
        ("CCCM", (67.72, 121.76, 194.62)),
        ("CCCK", (59.63, 114.56, 166.82)),
    ]
    for code, e in expected:
        g = got[code]
        assert max(abs(a - b) for a, b in zip(g, e)) <= 0.5, (code, g, e)


# RANDMIX5-H2C-A beige-safe materials (paper Table 4): slot letter,
# material, WB-corrected hex, fitted td_reference and k.
RANDMIX5_MATERIALS = [
    ("C", "Cyan slot: grey (Panchroma translucent)", "#7B7872", 3.443, 0.5006),
    ("M", "Magenta slot: magenta (Sunlu matte)", "#B43C74", 0.3742, 7.2382),
    ("Y", "Yellow slot: ice-blue (matte)", "#A9DDF3", 1.0902, 7.902),
    ("W", "White slot: beige (Bambu)", "#F6E5CC", 1.9719, 6.0686),
    ("K", "Key slot: purple (Bambu)", "#5950B4", 0.5938, 1.0591),
]
RANDMIX5_ALPHA_S = 6.0888
RANDMIX5_TD_SCALE = 3.4985
RANDMIX5_TD_GAMMA = 0.8039


def _randmix_colors(alpha_s=RANDMIX5_ALPHA_S, s=RANDMIX5_TD_SCALE, g=RANDMIX5_TD_GAMMA) -> Colors:
    from core.color_config import ColorConfig
    return Colors.from_configs([
        ColorConfig(name=name, hex=hex_, transmission_distance=td, k=k,
                    alpha_s=alpha_s, td_scale=s, td_gamma=g)
        for _, name, hex_, td, k in RANDMIX5_MATERIALS
    ])


def test_golden_cells_randmix5_beige_safe():
    colors = _randmix_colors()
    got = _predict(colors, ["CCCC"], 0.32)["CCCC"]
    e = (193.0, 191.16, 187.41)
    assert max(abs(a - b) for a, b in zip(got, e)) <= 0.5, (got, e)


# ---------------------------------------------------------------------------
# Reference-implementation cross-check (independent numpy of the paper forms)
# ---------------------------------------------------------------------------

def _reference_blend(colors: Colors, code: str, layer_height: float) -> tuple:
    """Independent implementation: per-layer transmission + Eqs. 4-8."""
    LN10 = float(np.log(10.0))
    remain = np.ones(3)
    loss = []
    for ch in code:
        color = colors[ch]
        A = (255.0 - np.array(color.rgb)) / 255.0
        if color.td_rgb is not None:
            mu = LN10 / np.array(color.td_rgb, dtype=float) + float(color.k) * A
        else:
            td_eff = color.td_scale * (float(color.td) ** color.td_gamma)
            mu = float(color.alpha_s) / td_eff + float(color.k) * A
        t = np.exp(-mu * layer_height)
        loss.append(remain * (1.0 - t))
        remain = remain * t
    loss.append(remain.copy())
    loss = np.array(loss)
    loss = loss / loss.sum(axis=0)
    rgb = np.ones(3)
    for i, ch in enumerate(code):
        rgb -= (255.0 - np.array(colors[ch].rgb)) / 255.0 * loss[i]
    out = loss[-1] * 1.0 + (1.0 - loss[-1]) * rgb
    return tuple(np.clip(out * 255.0, 0, 255))


@pytest.mark.parametrize("preset,layer_height", [
    ("bambu_cmywk_phase6", 0.32),
    ("bambu_cmyw_phase6", 0.32),
    ("clear_cmyg", 0.84),
    ("clear_cmyw", 0.84),
])
def test_reference_implementation_crosscheck(preset, layer_height):
    import itertools
    colors = Colors.from_configs(get_preset(preset))
    labels = colors.get_labels()
    codes = ["".join(c) for c in itertools.product(labels, repeat=4)][:64]
    got = _predict(colors, codes, layer_height)
    for code in codes:
        g = got[code]
        r = _reference_blend(colors, code, layer_height)
        assert max(abs(a - b) for a, b in zip(g, r)) < 1e-6, (preset, code, g, r)


# ---------------------------------------------------------------------------
# Full-artifact alignment (requires the research repo)
# ---------------------------------------------------------------------------

def _per_cell_rows(path: Path):
    with open(path) as f:
        return list(csv.DictReader(f))


@requires_research
def test_plate06_a_standard_full_cells():
    csv_path = RESEARCH / "data/results/PLATE-06-H2C-paper-matrix/runs/A-standard/per_cell_de.csv"
    rows = _per_cell_rows(csv_path)
    colors = Colors.from_configs(get_preset("bambu_cmywk_phase6"))
    got = _predict(colors, [r["code"] for r in rows], 0.32)
    worst = 0.0
    for r in rows:
        g = got[r["code"]]
        e = (float(r["pred_R"]), float(r["pred_G"]), float(r["pred_B"]))
        worst = max(worst, max(abs(a - b) for a, b in zip(g, e)))
    assert worst <= 0.5, f"worst |dRGB| {worst:.4f} over {len(rows)} cells"


@requires_research
def test_randmix5_beige_safe_full_cells():
    csv_path = RESEARCH / "data/results/RANDMIX5-H2C-fit/runs/A-beige-safe/per_cell_de.csv"
    rows = _per_cell_rows(csv_path)
    colors = _randmix_colors()
    got = _predict(colors, [r["code"] for r in rows], 0.32)
    worst = 0.0
    for r in rows:
        g = got[r["code"]]
        e = (float(r["pred_R"]), float(r["pred_G"]), float(r["pred_B"]))
        worst = max(worst, max(abs(a - b) for a, b in zip(g, e)))
    assert worst <= 0.5, f"worst |dRGB| {worst:.4f} over {len(rows)} cells"


def _read_clear_plate(plate_dir: Path, stem: str):
    """Parse the 16x16 code grid (row-major)."""
    codes = []
    with open(plate_dir / f"{stem}_code.csv") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            codes.extend(row)
    return codes


@pytest.mark.parametrize("preset,plate_dir,stem,layer_height", [
    ("clear_cmyg", "calibration/plates/clear_cmyg/CMYG_208x208x3.36", "CMYG_208x208x3.36", 0.84),
    ("clear_cmyw", "calibration/plates/clear_cmyw/CMYW_208x208x3.36", "CMYW_208x208x3.36", 0.84),
])
@requires_research
def test_clear_plate_codes_load_and_predict(preset, plate_dir, stem, layer_height):
    """Every designed code of the paper's clear plates blends without error
    under the app preset. (The *_rgb.csv beside them is measured photo
    pairing data, not model output — no prediction oracle there.)"""
    codes = _read_clear_plate(RESEARCH / plate_dir, stem)
    assert len(codes) == 256
    colors = Colors.from_configs(get_preset(preset))
    got = _predict(colors, codes, layer_height)
    for code in codes:
        rgb = got[code]
        assert len(rgb) == 3 and all(0.0 <= v <= 255.0 for v in rgb)


@requires_research
def test_clear_preset_td_data_matches_research():
    report = json.load(
        open(RESEARCH / "data/results/clear-plate-crossval/crossval_report.json")
    )
    for preset, key in (("clear_cmyg", "P07-def"), ("clear_cmyw", "P08-kxa")):
        prov = report[key]["provenance"]
        for cfg in get_preset(preset):
            lab = cfg.label
            assert cfg.td_rgb == pytest.approx(prov[lab]["td_rgb"], rel=1e-12), (preset, lab)
