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
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from skimage.color import rgb2lab

from core.blend_color import Colors, colors_key
from core.blend_models import codes_to_rgb_batch
from core.color_config import get_preset

# The research repo is referenced ONLY by this absolute path; no env
# overrides, no relative fallbacks. Tests skip cleanly when it is absent
# (CI runners).
RESEARCH = Path("/Users/gl/Dropbox/mine/projects/research/tinting-voxel-research")

requires_research = pytest.mark.skipif(
    not RESEARCH.exists(), reason=f"research repo not present: {RESEARCH}"
)

WHITE = (255, 255, 255)


def _predict(colors: Colors, codes: "list[str]", layer_height: float) -> "dict[str, tuple]":
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


def test_golden_cells_clear_staircase():
    """Inline clear anchors (full-precision engine values, P07-def /
    P08-kxa staircase characterizations at lh 0.84)."""
    p08 = Colors.from_configs(get_preset("clear_cmyw"))
    got = _predict(p08, ["WWWW", "CCCC"], 0.84)
    assert max(abs(a - b) for a, b in zip(got["WWWW"], (250.340795, 250.374672, 247.394385))) < 1e-3
    assert max(abs(a - b) for a, b in zip(got["CCCC"], (77.154814, 127.047109, 186.481179))) < 1e-3

    p07 = Colors.from_configs(get_preset("clear_cmyg"))
    got = _predict(p07, ["GGGG", "YYYG"], 0.84)
    assert max(abs(a - b) for a, b in zip(got["GGGG"], (160.162958, 158.993851, 156.303718))) < 1e-3
    assert max(abs(a - b) for a, b in zip(got["YYYG"], (218.739144, 203.782903, 114.043823))) < 1e-3


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
    under the app preset.

    NOTE on the research repo's *_rgb.csv: it is MEASURED photo pairing
    data, not model output — the app's predictions sit at mean dE00 ≈ 18.1
    from it (P07-def-w), squarely inside the paper's published
    model-vs-photo accuracy (dE_td_rgb 15.9-28.3). A <=0.5 per-cell
    prediction oracle against measured cells cannot exist even for the
    paper's own model; the independent prediction-side anchors are the
    provenance td_rgb equality (test_clear_preset_td_data_matches_research),
    the research-engine subprocess equivalence
    (test_clear_plates_match_research_engine), and the published-dE
    reproduction against the frozen measurement
    (test_clear_predictions_hit_published_measured_de)."""
    codes = _read_clear_plate(RESEARCH / plate_dir, stem)
    assert len(codes) == 256
    colors = Colors.from_configs(get_preset(preset))
    got = _predict(colors, codes, layer_height)
    for code in codes:
        rgb = got[code]
        assert len(rgb) == 3 and all(0.0 <= v <= 255.0 for v in rgb)


_ENGINE_PREDICT_SCRIPT = """
import csv, json, sys
research, plate_dir, stem, layer_height, bg = sys.argv[1:6]
sys.path.insert(0, research + "/engine/backend")
from core.color_materials import Color
from core.blend_models import _blend_by_mode

codes = []
with open(f"{research}/{plate_dir}/{stem}_code.csv") as f:
    rd = csv.reader(f); next(rd)
    for row in rd: codes.extend(row)

# Filament td_rgb data from the app preset, forwarded verbatim.
materials = json.loads(sys.argv[6])
cmap = {lab: Color(lab, m["td"], m["hex"], k=0.0, td_rgb=m["td_rgb"]) for lab, m in materials.items()}

out = [list(_blend_by_mode(c, float(layer_height), cmap, blend_mode="beer_lambert_td_rgb",
                           background_rgb=tuple(float(x) for x in bg.split(",")))) for c in codes]
print(json.dumps(out))
"""


def _read_clear_measured_grid(image_path: Path, side: int = 16) -> np.ndarray:
    """Sample the research-frozen MEASURED photo (fair-baselines image,
    e.g. P07-def-w_corrected.png) into a side x side per-cell mean grid —
    an oracle fully independent of the app."""
    img = np.asarray(Image.open(image_path).convert("RGB"), dtype=float)
    h, w = img.shape[:2]
    gy, gx = h // side, w // side
    grid = np.zeros((side, side, 3))
    for r in range(side):
        for c in range(side):
            grid[r, c] = img[r * gy:(r + 1) * gy, c * gx:(c + 1) * gx].reshape(-1, 3).mean(0)
    return grid


def _mean_de00(a: np.ndarray, b: np.ndarray) -> float:
    from skimage.color import deltaE_ciede2000

    la = rgb2lab(np.clip(np.asarray(a, float), 0, 255).reshape(-1, 1, 3) / 255.0)
    lb = rgb2lab(np.clip(np.asarray(b, float), 0, 255).reshape(-1, 1, 3) / 255.0)
    return float(deltaE_ciede2000(la, lb).mean())


@pytest.mark.parametrize("preset,plate_dir,stem,published_key", [
    ("clear_cmyg", "calibration/plates/clear_cmyg/CMYG_208x208x3.36",
     "CMYG_208x208x3.36", "P07-def-w"),
    ("clear_cmyw", "calibration/plates/clear_cmyw/CMYW_208x208x3.36",
     "CMYW_208x208x3.36", "P08-kxa-w"),
])
@requires_research
def test_clear_predictions_hit_published_measured_de(preset, plate_dir, stem, published_key):
    """Independent full-artifact anchor: the research repo freezes no
    per-cell ENGINE predictions for the clear plates, but it DOES freeze
    the measured photos the paper scored against (fair-baselines
    *_corrected.png images) and the published mean dE00 of the td_rgb
    model on them (dE_td_rgb). The app's predictions are compared per
    cell against the measured grid (block-mean sampled) and the mean dE00
    must reproduce the published value within 0.5 — preset or formula
    drift shifts the mean away. Orientation: the pairing grid rotation is
    sampled over the 4 rotations (the documented rot180/rot0 conventions
    hold after sampling; the minimum-over-rotations form guards against
    axis-order differences between the code grid and the photo)."""
    from PIL import Image  # noqa: F401  (used by _read_clear_measured_grid)

    baselines = json.load(
        open(RESEARCH / "data/results/clear-plate-fair-baselines/summary.json")
    )
    row = baselines["rows"][published_key]
    published = float(row["dE_td_rgb"])

    codes = _read_clear_plate(RESEARCH / plate_dir, stem)
    side = int(np.sqrt(len(codes)))
    measured = _read_clear_measured_grid(RESEARCH / row["image"], side)

    colors = Colors.from_configs(get_preset(preset))
    pred = np.array([
        codes_to_rgb_batch([c], 0.84, colors_key(colors), background_rgb=(255, 255, 255))[0]
        for c in codes
    ]).reshape(side, side, 3)

    best = min(_mean_de00(pred, np.rot90(measured, rot)) for rot in range(4))
    assert abs(best - published) <= 0.5, (
        f"{preset}: mean dE00 vs published measurement {best:.2f} vs {published:.2f} "
        f"(fair-baselines {published_key})"
    )


@pytest.mark.parametrize("preset,plate_dir,stem,layer_height", [
    ("clear_cmyg", "calibration/plates/clear_cmyg/CMYG_208x208x3.36", "CMYG_208x208x3.36", 0.84),
    ("clear_cmyw", "calibration/plates/clear_cmyw/CMYW_208x208x3.36", "CMYW_208x208x3.36", 0.84),
])
@requires_research
def test_clear_plates_match_research_engine(preset, plate_dir, stem, layer_height):
    """Direct research-engine comparison: run the engine's
    beer_lambert_td_rgb forward over the paper's plate codes (subprocess —
    both codebases own the `core` package name) and require the app's
    predictions to match per cell within 0.5."""
    import subprocess
    colors = Colors.from_configs(get_preset(preset))
    materials = {
        lab: {"td": colors[lab].td, "hex": colors[lab].hex, "td_rgb": list(colors[lab].td_rgb)}
        for lab in colors.get_labels()
    }
    proc = subprocess.run(
        [sys.executable, "-c", _ENGINE_PREDICT_SCRIPT,
         str(RESEARCH), plate_dir, stem, str(layer_height), "255,255,255",
         json.dumps(materials)],
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    engine = json.loads(proc.stdout)
    codes = _read_clear_plate(RESEARCH / plate_dir, stem)
    assert len(engine) == len(codes) == 256
    got = _predict(colors, codes, layer_height)
    worst = 0.0
    for code, e3 in zip(codes, engine):
        g = got[code]
        worst = max(worst, max(abs(a - b) for a, b in zip(g, e3)))
    assert worst <= 0.5, f"{preset}: worst |dRGB| {worst:.4f} vs research engine over {len(codes)} cells"


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
