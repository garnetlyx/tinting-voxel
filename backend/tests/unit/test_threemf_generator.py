"""Unit tests for 3MF generation service."""
import pytest
import zipfile
from io import BytesIO

from core.blend_color import Colors
from services.threemf_generator import generate_3mf


@pytest.fixture
def default_colors():
    return Colors()


@pytest.fixture
def simple_color_blocks():
    return [
        {
            'r': 0, 'g': 255, 'b': 255,
            'count': 2,
            'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}],
            'hex': '#00FFFF',
        },
        {
            'r': 255, 'g': 0, 'b': 255,
            'count': 1,
            'pixels': [{'x': 2, 'y': 0}],
            'hex': '#FF00FF',
        },
    ]


class TestGenerate3MF:
    """Tests for generate_3mf function."""

    def test_basic_output_is_bytes(self, simple_color_blocks, default_colors):
        """generate_3mf returns bytes."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
        )
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_output_is_valid_zip(self, simple_color_blocks, default_colors):
        """3MF is a ZIP archive."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
        )
        buf = BytesIO(result)
        assert zipfile.is_zipfile(buf)

    def test_3mf_contains_model(self, simple_color_blocks, default_colors):
        """3MF archive contains 3D/3dmodel.model XML file."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
        )
        buf = BytesIO(result)
        with zipfile.ZipFile(buf, 'r') as zf:
            names = zf.namelist()
            has_model = any('3dmodel.model' in n for n in names)
            assert has_model, f"Expected 3dmodel.model in archive, got: {names}"

    def test_empty_color_blocks_raises(self, default_colors):
        """Empty color blocks raises ValueError."""
        with pytest.raises(ValueError, match="No color blocks"):
            generate_3mf(
                color_blocks=[],
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                image_dimensions={'width': 4, 'height': 4},
                colors=default_colors,
            )

    def test_none_colors_raises(self, simple_color_blocks):
        """None colors raises ValueError."""
        with pytest.raises(ValueError, match="Colors instance is required"):
            generate_3mf(
                color_blocks=simple_color_blocks,
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                image_dimensions={'width': 4, 'height': 4},
                colors=None,
            )

    def test_with_color_hex_map(self, simple_color_blocks, default_colors):
        """3MF generation with color hex map succeeds."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            color_hex_map={'C': '#0086D6', 'M': '#EC008C', 'Y': '#F4EE2A', 'W': '#FFFFFF'},
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
