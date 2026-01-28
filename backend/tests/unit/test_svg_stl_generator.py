"""
Unit tests for SVG STL generator

Tests polygon triangulation, mesh extrusion, and STL generation.
"""
import numpy as np
import pytest

from services.svg_stl_generator import (
    triangulate_polygon,
    generate_polygon_mesh,
    generate_svg_stl_zip,
)
from services.stl_generator import initialize_color_mapping


class TestTriangulatePolygon:
    """Tests for ear clipping triangulation"""

    def test_triangle_returns_one_triangle(self):
        """Triangle should return single triangle"""
        polygon = [(0, 0), (1, 0), (0.5, 1)]
        triangles = triangulate_polygon(polygon)
        assert len(triangles) == 1
        assert triangles[0] == (0, 1, 2)

    def test_square_returns_two_triangles(self):
        """Square should return two triangles"""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        triangles = triangulate_polygon(polygon)
        assert len(triangles) == 2
        # Total area covered should equal 4 vertices - 2 = 2 triangles
        total_vertices = sum(3 for _ in triangles)
        assert total_vertices == 6

    def test_pentagon_returns_three_triangles(self):
        """Pentagon should return three triangles"""
        polygon = [(0, 0), (1, 0), (1.5, 0.5), (0.5, 1), (-0.5, 0.5)]
        triangles = triangulate_polygon(polygon)
        assert len(triangles) == 3

    def test_empty_polygon_returns_empty(self):
        """Empty polygon should return empty list"""
        triangles = triangulate_polygon([])
        assert len(triangles) == 0

    def test_two_points_returns_empty(self):
        """Two points should return empty list"""
        triangles = triangulate_polygon([(0, 0), (1, 1)])
        assert len(triangles) == 0

    def test_concave_polygon(self):
        """Concave polygon should triangulate correctly"""
        # L-shaped polygon
        polygon = [
            (0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)
        ]
        triangles = triangulate_polygon(polygon)
        # 6 vertices - 2 = 4 triangles
        assert len(triangles) == 4

    def test_triangle_indices_valid(self):
        """Triangle indices should be valid vertex references"""
        polygon = [(0, 0), (1, 0), (1, 1), (0.5, 0.8), (0, 1)]
        triangles = triangulate_polygon(polygon)
        for i, j, k in triangles:
            assert 0 <= i < len(polygon)
            assert 0 <= j < len(polygon)
            assert 0 <= k < len(polygon)


class TestGeneratePolygonMesh:
    """Tests for polygon extrusion to 3D mesh"""

    def test_triangle_produces_faces(self):
        """Triangle should produce bottom, top, and 3 side faces"""
        polygon = [(0, 0), (1, 0), (0.5, 1)]
        mesh = generate_polygon_mesh(polygon, z_min=0, z_max=1, pixel_size=1.0)

        # 1 triangle bottom + 1 triangle top + 3 edges * 2 triangles = 8 triangles
        assert mesh.shape[0] == 8
        assert mesh.shape[1] == 3  # 3 vertices per triangle
        assert mesh.shape[2] == 3  # 3 coordinates per vertex

    def test_square_produces_correct_faces(self):
        """Square should produce correct number of faces"""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        mesh = generate_polygon_mesh(polygon, z_min=0, z_max=0.5, pixel_size=1.0)

        # 2 triangles bottom + 2 triangles top + 4 edges * 2 triangles = 12 triangles
        assert mesh.shape[0] == 12

    def test_pixel_size_scaling(self):
        """Coordinates should be scaled by pixel_size"""
        polygon = [(0, 0), (10, 0), (10, 10), (0, 10)]
        mesh = generate_polygon_mesh(polygon, z_min=0, z_max=1, pixel_size=0.1)

        # Check that coordinates are scaled
        max_x = mesh[:, :, 0].max()
        max_y = mesh[:, :, 1].max()
        assert max_x == pytest.approx(1.0)  # 10 * 0.1
        assert max_y == pytest.approx(1.0)

    def test_z_range_correct(self):
        """Z coordinates should match z_min and z_max"""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        mesh = generate_polygon_mesh(polygon, z_min=0.5, z_max=1.5, pixel_size=1.0)

        z_coords = mesh[:, :, 2].flatten()
        assert z_coords.min() == pytest.approx(0.5)
        assert z_coords.max() == pytest.approx(1.5)

    def test_empty_polygon_returns_empty(self):
        """Empty polygon should return empty mesh"""
        mesh = generate_polygon_mesh([], z_min=0, z_max=1, pixel_size=1.0)
        assert mesh.shape == (0, 3, 3)

    def test_two_point_polygon_returns_empty(self):
        """Two-point polygon should return empty mesh"""
        mesh = generate_polygon_mesh([(0, 0), (1, 1)], z_min=0, z_max=1, pixel_size=1.0)
        assert mesh.shape == (0, 3, 3)


class TestGenerateSVGSTLZip:
    """Integration tests for SVG STL ZIP generation"""

    @pytest.fixture(autouse=True)
    def setup_color_mapping(self):
        """Initialize color mapping before tests"""
        initialize_color_mapping(layer_count=4, layer_height=0.08)

    def test_single_color_single_polygon(self):
        """Single color with single polygon should produce valid ZIP"""
        vector_results = [
            {
                'color': (255, 0, 0),  # Red
                'polygons': [[(0, 0), (10, 0), (10, 10), (0, 10)]],
                'pixel_count': 100,
                'polygon_points': 4
            }
        ]

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 20, 'height': 20}
        )

        assert len(zip_content) > 0
        # ZIP should contain some STL files
        assert zip_content[:2] == b'PK'  # ZIP magic number

    def test_multiple_colors_multiple_polygons(self):
        """Multiple colors with multiple polygons should work"""
        vector_results = [
            {
                'color': (255, 0, 0),
                'polygons': [
                    [(0, 0), (5, 0), (5, 5), (0, 5)],
                    [(10, 10), (15, 10), (15, 15), (10, 15)]
                ],
                'pixel_count': 50,
                'polygon_points': 8
            },
            {
                'color': (0, 255, 0),
                'polygons': [[(5, 5), (10, 5), (10, 10), (5, 10)]],
                'pixel_count': 25,
                'polygon_points': 4
            }
        ]

        zip_content = generate_svg_stl_zip(
            vector_results=vector_results,
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 20, 'height': 20}
        )

        assert len(zip_content) > 0

    def test_empty_vector_results(self):
        """Empty vector results should produce empty ZIP"""
        zip_content = generate_svg_stl_zip(
            vector_results=[],
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            image_dimensions={'width': 20, 'height': 20}
        )

        # Should still be a valid ZIP (just empty)
        assert zip_content[:2] == b'PK'


class TestTriangulationCorrectness:
    """Tests for triangulation correctness properties"""

    def test_triangles_cover_polygon_area(self):
        """Triangles should cover the same area as the polygon"""
        # Simple square: area = 1
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        triangles = triangulate_polygon(polygon)

        def triangle_area(t):
            i, j, k = t
            x1, y1 = polygon[i]
            x2, y2 = polygon[j]
            x3, y3 = polygon[k]
            return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2

        total_area = sum(triangle_area(t) for t in triangles)
        assert total_area == pytest.approx(1.0)

    def test_no_overlapping_triangles(self):
        """Triangles should not overlap (each vertex index used correctly)"""
        polygon = [(0, 0), (2, 0), (2, 2), (1, 1), (0, 2)]
        triangles = triangulate_polygon(polygon)

        # Check that all triangles have distinct indices
        for i, j, k in triangles:
            assert i != j and j != k and i != k


class TestMeshWinding:
    """Tests for mesh face winding order (for correct normals)"""

    def test_top_face_normals_point_up(self):
        """Top face triangles should have normals pointing up (positive Z)"""
        polygon = [(0, 0), (1, 0), (1, 1), (0, 1)]
        mesh = generate_polygon_mesh(polygon, z_min=0, z_max=1, pixel_size=1.0)

        # Find top face triangles (z = 1)
        for triangle in mesh:
            if all(v[2] == 1.0 for v in triangle):
                # Calculate normal
                v1, v2, v3 = triangle
                edge1 = v2 - v1
                edge2 = v3 - v1
                normal = np.cross(edge1, edge2)
                # Top face normal should point up
                assert normal[2] > 0 or np.allclose(normal, 0)
