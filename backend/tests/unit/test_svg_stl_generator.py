"""Tests for SVG STL generation from the printable pixel partition."""
import numpy as np
import pytest
import zipfile
from io import BytesIO

from services.svg_stl_generator import generate_svg_stl_zip
from core.blend_color import Colors


def test_svg_stl_and_3mf_use_identical_printable_partition(monkeypatch):
    from core.blend_color import Colors
    from services import svg_stl_generator, threemf_generator
    from services.vector_processor import finalize_vector_partition

    observed = {}

    def capture(format_name):
        def run(*args):
            result = finalize_vector_partition(*args)
            observed[format_name] = result.copy()
            return result
        return run

    monkeypatch.setattr(svg_stl_generator, 'finalize_vector_partition', capture('stl'))
    monkeypatch.setattr(threemf_generator, 'finalize_vector_partition', capture('3mf'))
    common = {
        'vector_results': [
            {'color': (255, 0, 0), 'regions': [
                {'outer': [(0, 0), (3, 0), (3, 7), (0, 7)], 'holes': []},
            ]},
            {'color': (0, 0, 255), 'regions': [
                {'outer': [(7, 0), (11, 0), (11, 7), (7, 7)], 'holes': []},
            ]},
        ],
        'layer_height': 0.08,
        'pixel_size': 0.2,
        'detail_size': 0.42,
        'layer_count': 4,
        'image_dimensions': {'width': 12, 'height': 8},
        'colors': Colors(),
        'white_backing_layers': 0,
    }
    stl = svg_stl_generator.generate_svg_stl_zip(**common)
    three = threemf_generator.generate_svg_3mf(**common)

    assert zipfile.is_zipfile(BytesIO(stl))
    assert zipfile.is_zipfile(BytesIO(three))
    np.testing.assert_array_equal(observed['stl'], observed['3mf'])
    assert set(np.unique(observed['stl'])) == {0, 1}


class TestGenerateSVGSTLZip:
    """Integration tests for SVG STL ZIP generation"""

    def test_single_color_single_region(self):
        """Single color with one region should produce valid ZIP."""
        vector_results = [
            {
                'color': (255, 0, 0),  # Red
                'regions': [{'outer': [(0, 0), (10, 0), (10, 10), (0, 10)], 'holes': []}],
                'pixel_count': 100,
                'polygon_points': 4
            }
        ]

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 20, 'height': 20},
            colors=Colors(),
        )

        assert len(zip_content) > 0
        # ZIP should contain some STL files
        assert zip_content[:2] == b'PK'  # ZIP magic number

    def test_multiple_colors_multiple_regions(self):
        """Multiple colors with multiple regions should work."""
        vector_results = [
            {
                'color': (255, 0, 0),
                'regions': [
                    {'outer': [(0, 0), (5, 0), (5, 5), (0, 5)], 'holes': []},
                    {'outer': [(10, 10), (15, 10), (15, 15), (10, 15)], 'holes': []},
                ],
                'pixel_count': 50,
                'polygon_points': 8
            },
            {
                'color': (0, 255, 0),
                'regions': [{'outer': [(5, 5), (10, 5), (10, 10), (5, 10)], 'holes': []}],
                'pixel_count': 25,
                'polygon_points': 4
            }
        ]

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 20, 'height': 20},
            colors=Colors(),
        )

        assert len(zip_content) > 0

    def test_regions_field_drives_svg_export(self):
        """SVG export uses region geometry with an interior hole."""
        vector_results = [
            {
                'color': (255, 0, 0),
                'regions': [
                    {
                        'outer': [(0, 0), (4, 0), (4, 4), (0, 4)],
                        'holes': [[(1, 1), (3, 1), (3, 3), (1, 3)]],
                    }
                ],
                'pixel_count': 12,
                'polygon_points': 8,
            }
        ]

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 5, 'height': 5},
            colors=Colors(),
        )

        assert zip_content[:2] == b'PK'

    def test_empty_vector_results(self):
        """Empty vector results are invalid for both SVG export formats."""
        with pytest.raises(ValueError, match='No vector results provided'):
            generate_svg_stl_zip(
                vector_results=[],
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
                image_dimensions={'width': 20, 'height': 20},
                colors=Colors(),
            )
