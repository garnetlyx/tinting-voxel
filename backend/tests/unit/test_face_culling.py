"""
Unit tests for Internal Face Culling algorithm

Tests the optimization that removes hidden faces between adjacent boxes
to reduce STL file size.
"""

from services.mesh_optimizer import (
    FaceDirection,
    build_adjacency_map,
    generate_box_with_culling,
    get_visible_faces,
)


class TestFaceDirection:
    """Tests for FaceDirection enum"""

    def test_all_directions_defined(self):
        """All six face directions should be defined"""
        assert FaceDirection.BOTTOM is not None
        assert FaceDirection.TOP is not None
        assert FaceDirection.LEFT is not None
        assert FaceDirection.RIGHT is not None
        assert FaceDirection.FRONT is not None
        assert FaceDirection.BACK is not None

    def test_direction_count(self):
        """Should have exactly 6 directions"""
        assert len(FaceDirection) == 6


class TestBuildAdjacencyMap:
    """Tests for building the adjacency map from rectangles"""

    def test_single_rectangle(self):
        """Single rectangle should have no neighbors"""
        rectangles = [(0, 0, 2, 2)]  # x, y, w, h
        adj_map = build_adjacency_map(rectangles)
        # Single rect at index 0
        assert 0 in adj_map
        # No neighbors in any direction
        neighbors = adj_map[0]
        assert not any(neighbors.values())

    def test_two_adjacent_horizontal(self):
        """Two horizontally adjacent rectangles should detect each other"""
        rectangles = [
            (0, 0, 2, 2),  # left rect
            (2, 0, 2, 2),  # right rect (touching at x=2)
        ]
        adj_map = build_adjacency_map(rectangles)

        # Left rect (index 0) should have right neighbor
        assert adj_map[0][FaceDirection.RIGHT]
        # Right rect (index 1) should have left neighbor
        assert adj_map[1][FaceDirection.LEFT]

    def test_two_adjacent_vertical(self):
        """Two vertically adjacent rectangles should detect each other"""
        rectangles = [
            (0, 0, 2, 2),  # bottom rect
            (0, 2, 2, 2),  # top rect (touching at y=2)
        ]
        adj_map = build_adjacency_map(rectangles)

        # Bottom rect should have back neighbor (higher y)
        assert adj_map[0][FaceDirection.BACK]
        # Top rect should have front neighbor (lower y)
        assert adj_map[1][FaceDirection.FRONT]

    def test_non_adjacent_rectangles(self):
        """Non-adjacent rectangles should have no neighbors"""
        rectangles = [
            (0, 0, 2, 2),   # bottom-left
            (5, 5, 2, 2),   # separate
        ]
        adj_map = build_adjacency_map(rectangles)

        # Neither should have neighbors
        assert not any(adj_map[0].values())
        assert not any(adj_map[1].values())

    def test_partial_overlap_not_adjacent(self):
        """Rectangles with partial edge overlap should still detect adjacency"""
        rectangles = [
            (0, 0, 3, 2),   # wide rect
            (3, 1, 2, 1),   # narrow rect touching at x=3, partial y overlap
        ]
        adj_map = build_adjacency_map(rectangles)

        # Left rect should have right neighbor (partial)
        assert adj_map[0][FaceDirection.RIGHT]


class TestGetVisibleFaces:
    """Tests for determining visible faces based on adjacency"""

    def test_no_neighbors_all_visible(self):
        """Rectangle with no neighbors should have all faces visible"""
        neighbors = dict.fromkeys(FaceDirection, False)
        visible = get_visible_faces(neighbors)
        assert all(visible.values())
        assert len(visible) == 6

    def test_right_neighbor_hides_right_face(self):
        """Right neighbor should hide the right face"""
        neighbors = dict.fromkeys(FaceDirection, False)
        neighbors[FaceDirection.RIGHT] = True
        visible = get_visible_faces(neighbors)
        assert visible[FaceDirection.RIGHT] is False
        # Other faces should still be visible
        assert visible[FaceDirection.LEFT] is True
        assert visible[FaceDirection.TOP] is True

    def test_all_neighbors_no_visible_side_faces(self):
        """Rectangle surrounded on all sides should only show top/bottom"""
        neighbors = {
            FaceDirection.LEFT: True,
            FaceDirection.RIGHT: True,
            FaceDirection.FRONT: True,
            FaceDirection.BACK: True,
            FaceDirection.TOP: False,  # Nothing above
            FaceDirection.BOTTOM: False,  # Nothing below
        }
        visible = get_visible_faces(neighbors)
        assert visible[FaceDirection.LEFT] is False
        assert visible[FaceDirection.RIGHT] is False
        assert visible[FaceDirection.FRONT] is False
        assert visible[FaceDirection.BACK] is False
        assert visible[FaceDirection.TOP] is True
        assert visible[FaceDirection.BOTTOM] is True


class TestGenerateBoxWithCulling:
    """Tests for generating box mesh with face culling"""

    def test_all_faces_generates_12_triangles(self):
        """Box with all faces should generate 12 triangles (2 per face)"""
        visible = dict.fromkeys(FaceDirection, True)
        mesh = generate_box_with_culling(
            xrange=(0, 1),
            yrange=(0, 1),
            zrange=(0, 1),
            visible_faces=visible
        )
        # 6 faces * 2 triangles = 12
        assert mesh.shape[0] == 12
        assert mesh.shape[1] == 3  # 3 vertices per triangle
        assert mesh.shape[2] == 3  # 3 coords per vertex

    def test_one_hidden_face_generates_10_triangles(self):
        """Box with one hidden face should generate 10 triangles"""
        visible = dict.fromkeys(FaceDirection, True)
        visible[FaceDirection.RIGHT] = False  # Hide right face
        mesh = generate_box_with_culling(
            xrange=(0, 1),
            yrange=(0, 1),
            zrange=(0, 1),
            visible_faces=visible
        )
        # 5 faces * 2 triangles = 10
        assert mesh.shape[0] == 10

    def test_two_hidden_faces_generates_8_triangles(self):
        """Box with two hidden faces should generate 8 triangles"""
        visible = dict.fromkeys(FaceDirection, True)
        visible[FaceDirection.LEFT] = False
        visible[FaceDirection.RIGHT] = False
        mesh = generate_box_with_culling(
            xrange=(0, 1),
            yrange=(0, 1),
            zrange=(0, 1),
            visible_faces=visible
        )
        # 4 faces * 2 triangles = 8
        assert mesh.shape[0] == 8

    def test_empty_box_returns_empty_mesh(self):
        """Box with all faces hidden should return empty mesh"""
        visible = dict.fromkeys(FaceDirection, False)
        mesh = generate_box_with_culling(
            xrange=(0, 1),
            yrange=(0, 1),
            zrange=(0, 1),
            visible_faces=visible
        )
        assert mesh.shape[0] == 0

    def test_box_dimensions_correct(self):
        """Generated box should have correct dimensions"""
        visible = dict.fromkeys(FaceDirection, True)
        mesh = generate_box_with_culling(
            xrange=(1, 3),
            yrange=(2, 5),
            zrange=(0, 2),
            visible_faces=visible
        )
        # Check that vertices are within expected bounds
        all_vertices = mesh.reshape(-1, 3)
        assert all_vertices[:, 0].min() >= 1  # x >= 1
        assert all_vertices[:, 0].max() <= 3  # x <= 3
        assert all_vertices[:, 1].min() >= 2  # y >= 2
        assert all_vertices[:, 1].max() <= 5  # y <= 5
        assert all_vertices[:, 2].min() >= 0  # z >= 0
        assert all_vertices[:, 2].max() <= 2  # z <= 2


class TestFaceCullingIntegration:
    """Integration tests for face culling with mesh generation"""

    def test_culling_reduces_triangle_count(self):
        """Face culling should reduce total triangle count for adjacent boxes"""
        # Two adjacent boxes without culling = 24 triangles
        # With culling = 22 triangles (2 hidden faces = -4 triangles, but each shared)
        # Actually: each box loses 1 face = 10 + 10 = 20 triangles

        rectangles = [
            (0, 0, 1, 1),  # left
            (1, 0, 1, 1),  # right
        ]

        adj_map = build_adjacency_map(rectangles)

        total_triangles = 0
        for idx, rect in enumerate(rectangles):
            visible = get_visible_faces(adj_map[idx])
            mesh = generate_box_with_culling(
                xrange=(rect[0], rect[0] + rect[2]),
                yrange=(rect[1], rect[1] + rect[3]),
                zrange=(0, 1),
                visible_faces=visible
            )
            total_triangles += mesh.shape[0]

        # Without culling: 12 + 12 = 24
        # With culling: 10 + 10 = 20 (each loses right/left face respectively)
        assert total_triangles == 20
        assert total_triangles < 24  # Less than no culling
