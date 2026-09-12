"""
Unit tests for Greedy Meshing algorithm

Tests the optimization that merges adjacent same-color pixels
into larger rectangular blocks to reduce STL file size.
"""
import numpy as np

from services.mesh_optimizer import (
    find_max_rectangle,
    greedy_mesh_2d,
    pixels_to_grid,
)


class TestPixelsToGrid:
    """Tests for converting pixel list to 2D grid"""

    def test_empty_pixels(self):
        """Empty pixel list should return empty grid"""
        pixels = []
        grid = pixels_to_grid(pixels, width=10, height=10)
        assert grid.shape == (10, 10)
        assert not grid.any()

    def test_single_pixel(self):
        """Single pixel should be placed correctly"""
        pixels = [{'x': 5, 'y': 3}]
        grid = pixels_to_grid(pixels, width=10, height=10)
        assert grid[3, 5]
        assert grid.sum() == 1

    def test_multiple_pixels(self):
        """Multiple pixels should all be placed correctly"""
        pixels = [
            {'x': 0, 'y': 0},
            {'x': 1, 'y': 0},
            {'x': 2, 'y': 0},
        ]
        grid = pixels_to_grid(pixels, width=10, height=10)
        assert grid[0, 0]
        assert grid[0, 1]
        assert grid[0, 2]
        assert grid.sum() == 3


class TestFindMaxRectangle:
    """Tests for finding maximum rectangle from a starting point"""

    def test_single_cell(self):
        """Single isolated cell should return 1x1 rectangle"""
        grid = np.zeros((5, 5), dtype=bool)
        grid[2, 2] = True
        rect = find_max_rectangle(grid, start_x=2, start_y=2)
        assert rect == (2, 2, 1, 1)  # x, y, width, height

    def test_horizontal_row(self):
        """Horizontal row should return correct width"""
        grid = np.zeros((5, 5), dtype=bool)
        grid[0, 0:3] = True  # 3 cells in a row
        rect = find_max_rectangle(grid, start_x=0, start_y=0)
        assert rect == (0, 0, 3, 1)

    def test_vertical_column(self):
        """Vertical column should return correct height"""
        grid = np.zeros((5, 5), dtype=bool)
        grid[0:3, 0] = True  # 3 cells in a column
        rect = find_max_rectangle(grid, start_x=0, start_y=0)
        assert rect == (0, 0, 1, 3)

    def test_full_rectangle(self):
        """Full rectangle should be detected"""
        grid = np.zeros((5, 5), dtype=bool)
        grid[1:4, 1:4] = True  # 3x3 block
        rect = find_max_rectangle(grid, start_x=1, start_y=1)
        assert rect == (1, 1, 3, 3)


class TestGreedyMesh2D:
    """Tests for the main greedy meshing algorithm"""

    def test_empty_grid(self):
        """Empty grid should return no rectangles"""
        grid = np.zeros((10, 10), dtype=bool)
        rects = greedy_mesh_2d(grid)
        assert len(rects) == 0

    def test_single_pixel(self):
        """Single pixel should return single 1x1 rectangle"""
        grid = np.zeros((10, 10), dtype=bool)
        grid[5, 5] = True
        rects = greedy_mesh_2d(grid)
        assert len(rects) == 1
        assert rects[0] == (5, 5, 1, 1)

    def test_contiguous_block(self):
        """Contiguous 3x3 block should return single rectangle"""
        grid = np.zeros((10, 10), dtype=bool)
        grid[0:3, 0:3] = True
        rects = greedy_mesh_2d(grid)
        # Should merge into single rectangle
        assert len(rects) == 1
        total_area = sum(w * h for _, _, w, h in rects)
        assert total_area == 9

    def test_separate_blocks(self):
        """Two separate blocks should return two rectangles"""
        grid = np.zeros((10, 10), dtype=bool)
        grid[0:2, 0:2] = True  # 2x2 block at top-left
        grid[5:7, 5:7] = True  # 2x2 block at center
        rects = greedy_mesh_2d(grid)
        assert len(rects) == 2
        total_area = sum(w * h for _, _, w, h in rects)
        assert total_area == 8

    def test_l_shaped_region(self):
        """L-shaped region should be decomposed into rectangles"""
        grid = np.zeros((5, 5), dtype=bool)
        # L shape:
        # X X X
        # X . .
        # X . .
        grid[0, 0:3] = True  # top row
        grid[1:3, 0] = True  # left column
        rects = greedy_mesh_2d(grid)
        # Should decompose into 2 rectangles
        total_area = sum(w * h for _, _, w, h in rects)
        assert total_area == 5
        assert len(rects) >= 1  # At least 1 rectangle

    def test_all_pixels_covered(self):
        """All set pixels should be covered by output rectangles"""
        grid = np.zeros((10, 10), dtype=bool)
        # Random pattern
        grid[1, 1] = True
        grid[1, 2] = True
        grid[3, 5] = True
        grid[7, 8] = True

        rects = greedy_mesh_2d(grid)

        # Verify coverage by reconstructing
        covered = np.zeros_like(grid)
        for x, y, w, h in rects:
            covered[y:y+h, x:x+w] = True

        assert np.array_equal(grid, covered)


class TestMeshOptimizationIntegration:
    """Integration tests for mesh optimization with STL generator"""

    def test_optimization_reduces_box_count(self, sample_pixel_map):
        """Optimized meshing should produce fewer boxes than per-pixel"""
        # Convert fixture to grid format
        width = max(x for x, _ in sample_pixel_map.keys()) + 1
        height = max(y for _, y in sample_pixel_map.keys()) + 1
        grid = np.zeros((height, width), dtype=bool)
        for (x, y), _ in sample_pixel_map.items():
            grid[y, x] = True

        # Without optimization: 13 boxes (one per pixel)
        pixel_count = len(sample_pixel_map)

        # With optimization: should be fewer rectangles
        rects = greedy_mesh_2d(grid)

        assert len(rects) < pixel_count
        # Verify total area matches
        total_area = sum(w * h for _, _, w, h in rects)
        assert total_area == pixel_count


class TestFindMaxRectangleEdgeCases:
    """Edge case tests for find_max_rectangle"""

    def test_start_on_empty_cell(self):
        """Starting on empty cell should return zero-size rectangle"""
        grid = np.zeros((5, 5), dtype=bool)
        rect = find_max_rectangle(grid, start_x=2, start_y=2)
        assert rect == (2, 2, 0, 0)

    def test_boundary_conditions(self):
        """Rectangle at grid boundary should not overflow"""
        grid = np.zeros((3, 3), dtype=bool)
        grid[2, 2] = True  # bottom-right corner
        rect = find_max_rectangle(grid, start_x=2, start_y=2)
        assert rect == (2, 2, 1, 1)


class TestGenerateOptimizedBoxes:
    """Tests for the generate_optimized_boxes function"""

    def test_empty_pixels(self):
        """Empty pixel list should return empty boxes list"""
        from services.mesh_optimizer import generate_optimized_boxes
        boxes = generate_optimized_boxes(
            pixels=[],
            width=10, height=10,
            pixel_size=1.0,
            z_min=0.0, z_max=1.0
        )
        assert len(boxes) == 0

    def test_single_pixel_box(self):
        """Single pixel should return single box with correct dimensions"""
        from services.mesh_optimizer import generate_optimized_boxes
        pixels = [{'x': 5, 'y': 3}]
        boxes = generate_optimized_boxes(
            pixels=pixels,
            width=10, height=10,
            pixel_size=0.5,
            z_min=0.0, z_max=0.08
        )
        assert len(boxes) == 1
        xrange, yrange, zrange = boxes[0]
        assert xrange == (2.5, 3.0)  # 5 * 0.5, 6 * 0.5
        assert yrange == (1.5, 2.0)  # 3 * 0.5, 4 * 0.5
        assert zrange == (0.0, 0.08)

    def test_merged_pixels_box(self):
        """Adjacent pixels should merge into single larger box"""
        from services.mesh_optimizer import generate_optimized_boxes
        pixels = [
            {'x': 0, 'y': 0},
            {'x': 1, 'y': 0},
            {'x': 0, 'y': 1},
            {'x': 1, 'y': 1},
        ]
        boxes = generate_optimized_boxes(
            pixels=pixels,
            width=10, height=10,
            pixel_size=1.0,
            z_min=0.0, z_max=1.0
        )
        # 2x2 grid should merge into single box
        assert len(boxes) == 1
        xrange, yrange, zrange = boxes[0]
        assert xrange == (0.0, 2.0)
        assert yrange == (0.0, 2.0)

    def test_separate_pixels_multiple_boxes(self):
        """Non-adjacent pixels should produce multiple boxes"""
        from services.mesh_optimizer import generate_optimized_boxes
        pixels = [
            {'x': 0, 'y': 0},
            {'x': 5, 'y': 5},
        ]
        boxes = generate_optimized_boxes(
            pixels=pixels,
            width=10, height=10,
            pixel_size=1.0,
            z_min=0.0, z_max=1.0
        )
        assert len(boxes) == 2

    def test_max_rectangles_cap_aborts_noise(self):
        """The memory-budget cap must abort pathological grids instead of
        materializing an unbounded rectangle list."""
        import numpy as np
        import pytest
        from services.mesh_optimizer import greedy_mesh_2d, MeshTooComplexError

        yy, xx = np.mgrid[0:120, 0:100]
        checker = (xx + yy) % 2 == 0
        with pytest.raises(MeshTooComplexError):
            greedy_mesh_2d(checker, max_rectangles=50)

    def test_no_cap_keeps_original_behavior(self):
        """Without a cap the meshing result is unchanged."""
        import numpy as np
        from services.mesh_optimizer import greedy_mesh_2d

        yy, xx = np.mgrid[0:120, 0:100]
        checker = (xx + yy) % 2 == 0
        rects = greedy_mesh_2d(checker)
        assert len(rects) == int(checker.sum())
