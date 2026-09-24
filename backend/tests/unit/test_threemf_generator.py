"""Unit tests for 3MF generation service."""
import pytest
import zipfile
from io import BytesIO

from core.blend_color import Colors
from services.threemf_generator import generate_3mf
from tests.label_maps import labels_from_blocks


def test_svg_3mf_uses_selected_backing_and_detail_size(monkeypatch, default_colors):
    from services import threemf_generator

    observed = {}
    compute = threemf_generator.compute_reference_matrices
    finalize = threemf_generator.finalize_vector_partition

    def capture_matrix(*args, **kwargs):
        observed['matrix'] = kwargs
        return compute(*args, **kwargs)

    def capture_partition(*args):
        observed['partition'] = args
        return finalize(*args)

    monkeypatch.setattr(threemf_generator, 'compute_reference_matrices', capture_matrix)
    monkeypatch.setattr(threemf_generator, 'finalize_vector_partition', capture_partition)
    result = threemf_generator.generate_svg_3mf(
        vector_results=[{
            'color': (255, 0, 0),
            'regions': [{'outer': [(0, 0), (4, 0), (4, 4), (0, 4)], 'holes': []}],
        }],
        layer_height=0.08,
        pixel_size=0.2,
        layer_count=4,
        image_dimensions={'width': 5, 'height': 5},
        colors=default_colors,
        white_backing_layers=2,
        backing_mode='black',
        detail_size=0.82,
    )
    assert zipfile.is_zipfile(BytesIO(result))
    assert observed['matrix']['backing_layers'] == 2
    assert observed['matrix']['backing_mode'] == 'black'
    assert observed['partition'][2:] == (0.2, 0.82)


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
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
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
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
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
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
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
                labels=labels_from_blocks([], 4, 4),
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
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
                labels=labels_from_blocks(simple_color_blocks, 4, 4),
                colors=None,
            )

    def test_with_color_hex_map(self, simple_color_blocks, default_colors):
        """3MF generation with color hex map succeeds."""
        result = generate_3mf(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            labels=labels_from_blocks(simple_color_blocks, 4, 4),
            colors=default_colors,
            color_hex_map={'C': '#0086D6', 'M': '#EC008C', 'Y': '#F4EE2A', 'W': '#FFFFFF'},
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
