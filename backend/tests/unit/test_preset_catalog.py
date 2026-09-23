"""Catalog boundaries and frontend/backend parameter parity."""
from dataclasses import asdict

import pytest
from pydantic import ValidationError

from api.models import FilamentPreset, FilamentPreviewRequest
from core.color_config import PRESETS, get_available_presets, get_preset


def test_catalog_exposes_one_material_contract():
    for colors in PRESETS.values():
        for material in colors:
            assert set(asdict(material)) == {"name", "hex", "transmission_distance"}
    assert [preset.value for preset in FilamentPreset] == get_available_presets()


@pytest.mark.parametrize("name", ["bambu_cmyk", "bambu_cmyk_calibrated",
    "bambu_cmyk_per_channel_k", "clear_cmywg",
    "bambu", "clear", "clear_cmyk"])
def test_removed_presets_are_rejected(name):
    assert get_preset(name) is None
    with pytest.raises(ValidationError):
        FilamentPreviewRequest(filamentPreset=name)


@pytest.mark.parametrize("name", ["bambu_cmyw", "bambu_cmywk"])
def test_bambu_catalog_uses_measured_channels_from_one_material_set(name):
    full = {material.label: material for material in get_preset("bambu_cmywk")}
    for material in get_preset(name):
        td = material.transmission_distance
        assert isinstance(td, tuple) and len(td) == 3
        assert len(set(td)) > 1
        assert material is full[material.label]
