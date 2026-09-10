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
    # Contract: the fixture carries every backend field except k_rgb
    # (backend-only). td_rgb is part of the frontend contract; tuples are
    # normalized to lists to match the JSON representation.
    def _norm(value):
        return list(value) if isinstance(value, tuple) else value

    actual = {name: [{key: _norm(value) for key, value in asdict(c).items()
                      if value is not None and key != "k_rgb"} for c in colors]
              for name, colors in PRESETS.items()}
    assert actual == expected
    assert get_available_presets() == ["bambu_cmywk_phase6", "bambu_cmyw_phase6", "clear_cmywg"]
    assert [preset.value for preset in FilamentPreset] == get_available_presets()


@pytest.mark.parametrize("name", ["bambu_cmyk", "bambu_cmyk_calibrated",
    "bambu_cmyk_phase6", "bambu_cmyk_per_channel_k", "clear_cmyg", "clear_cmyw",
    "bambu", "clear", "clear_cmyk"])
def test_removed_presets_are_rejected(name):
    assert get_preset(name) is None
    with pytest.raises(ValidationError):
        FilamentPreviewRequest(filamentPreset=name)
