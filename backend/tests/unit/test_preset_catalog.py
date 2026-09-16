"""Catalog boundaries and frontend/backend parameter parity."""
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.models import FilamentPreset, FilamentPreviewRequest
from core.color_config import PRESETS, get_available_presets, get_preset


def test_catalog_matches_frontend_fixture():
    expected = json.loads((Path(__file__).parents[3] / "src/api/__fixtures__/filament-presets.json").read_text())
    # Contract: the fixture carries exactly the surviving schema
    # (name, hex, transmission_distance, k, and the scalar-form compensation
    # triple when non-neutral). Neutral values (alpha_s = ln 10,
    # td_scale = td_gamma = 1) are omitted on both sides — they equal the
    # schema defaults and are unused in the per-channel (td_rgb) branch.
    LN10 = 2.302585092994046

    def _norm(value):
        return list(value) if isinstance(value, tuple) else value

    def _row(config):
        d = {key: _norm(value) for key, value in asdict(config).items()
             if value is not None}
        if d.get("alpha_s") == LN10 and d.get("td_scale") == 1.0 and d.get("td_gamma") == 1.0:
            d.pop("alpha_s"), d.pop("td_scale"), d.pop("td_gamma")
        return d

    actual = {name: [_row(c) for c in colors] for name, colors in PRESETS.items()}
    assert actual == expected
    assert get_available_presets() == ["bambu_cmywk_phase6", "bambu_cmyw_phase6", "clear_cmyg", "clear_cmyw"]
    assert [preset.value for preset in FilamentPreset] == get_available_presets()


@pytest.mark.parametrize("name", ["bambu_cmyk", "bambu_cmyk_calibrated",
    "bambu_cmyk_per_channel_k", "clear_cmywg",
    "bambu", "clear", "clear_cmyk"])
def test_removed_presets_are_rejected(name):
    assert get_preset(name) is None
    with pytest.raises(ValidationError):
        FilamentPreviewRequest(filamentPreset=name)
