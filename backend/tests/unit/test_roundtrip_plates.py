"""Pipeline contract: mapped codes retain the selected material's channel TD."""
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from core.blend_color import BlendTestGenerator, Colors
from core.color_config import PRESETS
from services.image_processor import process_image


@pytest.mark.parametrize("preset,layer_height", [
    ("bambu_cmywk", .08), ("bambu_cmyw", .08),
    ("clear_cmyg", .84), ("clear_cmyw", .84),
])
def test_pipeline_assigned_codes_match_the_selected_model(preset, layer_height):
    pixels = np.array([[(220, 45, 70), (40, 150, 210)],
                       [(250, 245, 225), (40, 50, 65)]], dtype=np.uint8)
    image = Image.fromarray(pixels).resize((24, 24), Image.Resampling.NEAREST)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    colors = Colors.from_configs(PRESETS[preset])
    result = process_image(
        image_bytes=buffer.getvalue(), max_colors=4, color_threshold=0,
        pixel_size=.15, filament_colors=colors, layer_count=4,
        layer_height=layer_height, white_backing_layers=0, detail_size=None,
    )
    palette = result["mappedBlendPalette"]
    assert len(palette) == 4
    generator = BlendTestGenerator(colors=colors, layer_height=layer_height)
    for entry in palette:
        code = entry["code"]
        assert len(code) == 4 and set(code) <= set(colors.get_labels())
        expected = np.round(generator.code_to_rgb(code)).astype(int)
        np.testing.assert_allclose(entry["rgb"], expected, atol=1)
