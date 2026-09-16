"""Round-trip acceptance: paper simulated plate image in, color codes out.

For each paper benchmark (PLATE-06 A-standard, RANDMIX5, Clear CMYG P07-def,
Clear CMYW P08-kxa) the test renders the paper's simulated plate — one grid
cell per code, filled with the model-predicted color quantized to 8-bit —
and feeds it through the REAL processing pipeline (unique-color extraction,
threshold merging, reference-matrix nearest-code search). The assigned code
per cell must recover the paper's designed code:

- 8-bit separable cells (no other code in the app's full search space at
  that stack length shares the quantized color): exact code match, 100%
  required.
- Collision cells (an identical quantized color in the full search space;
  e.g. near-opaque stacks where the top layer is invisible, like KKKC vs
  KKKM): the assigned code must be render-equivalent — its own quantized
  prediction equals the designed code's quantized prediction.

Codes are grouped by stack length and each length runs with layer_count
equal to it: the app's model space for one job is fixed-length codes, and
the plate's 1-3 layer cells are recovered at their own depth.

The plate codes come from the research repo directly (no copies here);
the whole module skips when the repo is absent (CI).
"""
import csv
import itertools
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.blend_color import BlendTestGenerator, Colors
from core.color_config import get_preset
from services.image_processor import process_image
from tests.unit.test_paper_alignment import RESEARCH, _randmix_colors, _read_clear_plate

pytestmark = pytest.mark.skipif(
    not RESEARCH.exists(), reason=f"research repo not present: {RESEARCH}"
)

CELL_PX = 8


def _plate_codes(which: str) -> list[str]:
    """Load benchmark codes from the research repo."""
    if which == "plate06_a_standard":
        path = RESEARCH / "data/results/PLATE-06-H2C-paper-matrix/runs/A-standard/per_cell_de.csv"
    elif which == "randmix5_a_beige_safe":
        path = RESEARCH / "data/results/RANDMIX5-H2C-fit/runs/A-beige-safe/per_cell_de.csv"
    elif which == "clear_cmyg_p07_def":
        return _read_clear_plate(
            RESEARCH / "calibration/plates/clear_cmyg/CMYG_208x208x3.36",
            "CMYG_208x208x3.36",
        )
    elif which == "clear_cmyw_p08_kxa":
        return _read_clear_plate(
            RESEARCH / "calibration/plates/clear_cmyw/CMYW_208x208x3.36",
            "CMYW_208x208x3.36",
        )
    else:
        raise ValueError(which)
    with open(path, encoding="utf-8") as fh:
        return [r["code"] for r in csv.DictReader(fh)]


def _quantized(rgb: np.ndarray) -> tuple[int, int, int]:
    return tuple(int(c) for c in np.clip(np.round(rgb), 0, 255))


BENCHMARKS = [
    pytest.param(
        "plate06_a_standard",
        lambda: Colors.from_configs(get_preset("bambu_cmywk_phase6")),
        0.32, id="plate06_a_standard",
    ),
    pytest.param(
        "randmix5_a_beige_safe",
        _randmix_colors,
        0.32, id="randmix5_a_beige_safe",
    ),
    pytest.param(
        "clear_cmyg_p07_def",
        lambda: Colors.from_configs(get_preset("clear_cmyg")),
        0.84, id="clear_cmyg_p07_def",
    ),
    pytest.param(
        "clear_cmyw_p08_kxa",
        lambda: Colors.from_configs(get_preset("clear_cmyw")),
        0.84, id="clear_cmyw_p08_kxa",
    ),
]


@pytest.mark.parametrize("fixture,colors_fn,layer_height", BENCHMARKS)
def test_roundtrip_paper_plates(fixture, colors_fn, layer_height):
    codes = _plate_codes(fixture)
    colors = colors_fn()
    gen = BlendTestGenerator(
        colors=colors, layer_height=layer_height, layer_count_max=4, verbose=False,
    )
    labels = colors.get_labels()

    exact = equivalent = 0
    failures: list[str] = []
    total = 0

    by_length: dict[int, list[str]] = {}
    for code in codes:
        by_length.setdefault(len(code), []).append(code)

    for length, length_codes in sorted(by_length.items()):
        # Full search space at this stack length: every ordering the app can
        # assign. Separability and collisions are judged across it.
        full_space = ["".join(p) for p in itertools.product(labels, repeat=length)]
        pred = {c: np.asarray(gen.code_to_rgb(c), dtype=np.float64) for c in full_space}
        quant = {c: _quantized(pred[c]) for c in full_space}
        color_groups: dict[tuple[int, int, int], list[str]] = {}
        for c in full_space:
            color_groups.setdefault(quant[c], []).append(c)
        separable = {
            c for c in full_space if len(color_groups[quant[c]]) == 1
        }

        # Render the simulated plate for the length's cells.
        n = len(length_codes)
        cols = int(np.ceil(np.sqrt(n)))
        rows = int(np.ceil(n / cols))
        # White background (the app's transparent = white convention) so
        # trailing empty slots never introduce a phantom color block.
        img = np.full((rows * CELL_PX, cols * CELL_PX, 3), 255, dtype=np.uint8)
        for i, code in enumerate(length_codes):
            r, c = divmod(i, cols)
            img[r * CELL_PX:(r + 1) * CELL_PX, c * CELL_PX:(c + 1) * CELL_PX] = \
                np.clip(np.round(pred[code]), 0, 255).astype(np.uint8)
        buf = BytesIO()
        Image.fromarray(img).save(buf, format="PNG")

        n_unique_in_image = len(np.unique(img.reshape(-1, 3), axis=0))
        result = process_image(
            image_bytes=buf.getvalue(),
            max_colors=n_unique_in_image,
            color_threshold=0,
            pixel_size=0.15,
            filament_colors=colors,
            layer_count=length,
            layer_height=layer_height,
            white_backing_layers=0,
            detail_size=None,
        )
        lookup = {
            tuple(entry["sourceRgb"]): entry["code"]
            for entry in result["mappedBlendPalette"]
        }

        img_arr = np.array(Image.open(BytesIO(buf.getvalue())))
        for i, code in enumerate(length_codes):
            r, c = divmod(i, cols)
            y = r * CELL_PX + CELL_PX // 2
            x = c * CELL_PX + CELL_PX // 2
            pixel = tuple(int(v) for v in img_arr[y, x])
            assert pixel in lookup, (
                f"{fixture} L{length}: cell {i} pixel {pixel} has no mapped code"
            )
            assigned = lookup[pixel]
            total += 1
            if assigned == code:
                exact += 1
            elif quant[assigned] == quant[code]:
                equivalent += 1
                if code in separable:
                    failures.append(
                        f"L{length} cell {i} code {code}: separable but got "
                        f"render-equivalent {assigned}"
                    )
            else:
                failures.append(
                    f"L{length} cell {i} code {code}: got {assigned} "
                    f"(quant {quant[assigned]}, designed {quant[code]})"
                )

    print(
        f"\n{fixture} round-trip: {total} cells, exact={exact} "
        f"({100.0 * exact / total:.1f}%), render-equivalent={equivalent}"
    )
    if fixture == "clear_cmyg_p07_def":
        # The user's own filament set: zero 8-bit collisions in the paper
        # data — every cell must recover its exact designed code.
        assert exact == 256, f"clear CMYG must round-trip 256/256, got {exact}"
    assert not failures, (
        f"{fixture}: {len(failures)} mismatches (first 10): {failures[:10]}"
    )
