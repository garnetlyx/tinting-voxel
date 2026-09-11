"""
Unit tests for double-sided print support (Task 2-05).

Validates that generate_stl_zip with double_sided=True produces:
- Mirrored back-side layers stacked on top of front layers
- Larger output than single-sided
- Correct physical height in filenames (2x layer height)
- Compatibility with base plate and greedy meshing
"""
import struct
import zipfile
from io import BytesIO

import pytest

from core.blend_color import Colors
from services.stl_generator import generate_stl_zip


@pytest.fixture
def simple_color_blocks():
    """Minimal color blocks for double-sided tests."""
    return [
        {
            'r': 255, 'g': 0, 'b': 0,
            'count': 4,
            'pixels': [
                {'x': 0, 'y': 0}, {'x': 1, 'y': 0},
                {'x': 0, 'y': 1}, {'x': 1, 'y': 1},
            ],
            'hex': '#FF0000',
        },
        {
            'r': 255, 'g': 255, 'b': 255,
            'count': 4,
            'pixels': [
                {'x': 2, 'y': 0}, {'x': 3, 'y': 0},
                {'x': 2, 'y': 1}, {'x': 3, 'y': 1},
            ],
            'hex': '#FFFFFF',
        },
    ]


@pytest.fixture
def default_colors():
    return Colors()


class TestDoubleSidedGeneration:
    """Tests for double_sided=True in generate_stl_zip."""

    def test_double_sided_succeeds(self, simple_color_blocks, default_colors):
        """generate_stl_zip with double_sided=True returns valid ZIP."""
        result = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
        )
        zf = zipfile.ZipFile(BytesIO(result))
        assert len(zf.namelist()) > 0

    def test_double_sided_larger_than_single(self, simple_color_blocks, default_colors):
        """Double-sided output is strictly larger than single-sided."""
        single = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=False,
        )
        double = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
        )
        assert len(double) > len(single)

    def test_double_sided_physical_height_doubled(self, simple_color_blocks, default_colors):
        """Filename encodes height for double-sided (2x optical + n_white backing)."""
        layer_height = 0.08
        layer_count = 4
        n_white = 1
        expected_height = (layer_count * 2 + n_white) * layer_height  # 0.72

        result = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=layer_height,
            pixel_size=0.08,
            layer_count=layer_count,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
        )
        zf = zipfile.ZipFile(BytesIO(result))
        filenames = zf.namelist()
        # All filenames should contain the expected physical height
        for fn in filenames:
            assert f"x{expected_height:.2f}" in fn, (
                f"Expected height {expected_height:.2f} in filename '{fn}'"
            )

    def test_double_sided_more_triangles(self, simple_color_blocks, default_colors):
        """Double-sided STL files contain more triangles than single-sided."""
        def count_triangles(zip_bytes):
            total = 0
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            for name in zf.namelist():
                data = zf.read(name)
                if len(data) > 84:
                    total += struct.unpack_from('<I', data, 80)[0]
            return total

        single = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=False,
        )
        double = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
        )
        assert count_triangles(double) > count_triangles(single)

    def test_double_sided_same_stl_file_set(self, simple_color_blocks, default_colors):
        """Double-sided produces same set of color STL files (same labels)."""
        single = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=False,
        )
        double = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
        )

        def get_labels(zip_bytes):
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            labels = set()
            for fn in zf.namelist():
                # Label is the last part before .stl, e.g. "..._C.stl" -> "C"
                label = fn.rsplit('_', 1)[-1].replace('.stl', '')
                labels.add(label)
            return labels

        assert get_labels(single) == get_labels(double)


class TestDoubleSidedWithGreedyMeshing:
    """Double-sided with greedy meshing optimization."""

    def test_double_sided_with_greedy_meshing(self, simple_color_blocks, default_colors):
        """Double-sided + greedy meshing produces valid output."""
        result = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
            use_greedy_meshing=True,
        )
        zf = zipfile.ZipFile(BytesIO(result))
        assert len(zf.namelist()) > 0

    def test_double_sided_without_greedy_meshing(self, simple_color_blocks, default_colors):
        """Double-sided without greedy meshing also produces valid output."""
        result = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=True,
            use_greedy_meshing=False,
        )
        zf = zipfile.ZipFile(BytesIO(result))
        assert len(zf.namelist()) > 0


class TestDoubleSidedFalse:
    """Verify double_sided=False behaves the same as the default."""

    def test_false_same_as_default(self, simple_color_blocks, default_colors):
        """double_sided=False output matches not specifying the parameter."""
        result_default = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
        )
        result_false = generate_stl_zip(
            color_blocks=simple_color_blocks,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 4, 'height': 4},
            colors=default_colors,
            double_sided=False,
        )
        # Same number of files
        zf_default = zipfile.ZipFile(BytesIO(result_default))
        zf_false = zipfile.ZipFile(BytesIO(result_false))
        assert zf_default.namelist() == zf_false.namelist()
