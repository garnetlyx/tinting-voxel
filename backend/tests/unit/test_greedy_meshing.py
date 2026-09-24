"""
Unit tests for Greedy Meshing algorithm

Tests the optimization that merges adjacent same-color pixels
into larger rectangular blocks to reduce STL file size.
"""
import numpy as np

from services.mesh_optimizer import greedy_mesh_2d
from services.stl_generator import block_box_runs


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


class TestBlockBoxRuns:
    """Footprint meshing and extrusion of color blocks from a label map"""

    @staticmethod
    def _labels(cells: list[tuple[int, int]], width: int = 10, height: int = 10) -> np.ndarray:
        labels = np.full((height, width), 255, dtype=np.uint8)
        for x, y in cells:
            labels[y, x] = 0
        return labels

    def test_empty_block(self):
        """A block with no cells yields no boxes"""
        assert list(block_box_runs(self._labels([]), ['C'], 1.0, 1.0)) == []

    def test_single_pixel_box(self):
        """Single pixel should return single box with correct dimensions"""
        runs = list(block_box_runs(self._labels([(5, 3)]), ['C'], 0.5, 0.08))
        assert [(code, cells) for code, _, cells in runs] == [('C', 1)]
        assert runs[0][1] == [((2.5, 3.0), (1.5, 2.0), (0.0, 0.08))]

    def test_merged_pixels_box(self):
        """Adjacent pixels should merge into single larger box"""
        runs = list(block_box_runs(self._labels([(0, 0), (1, 0), (0, 1), (1, 1)]), ['C'], 1.0, 1.0))
        assert runs[0][1] == [((0.0, 2.0), (0.0, 2.0), (0.0, 1.0))]

    def test_separate_pixels_multiple_boxes(self):
        """Non-adjacent pixels should produce multiple boxes"""
        runs = list(block_box_runs(self._labels([(0, 0), (5, 5)]), ['C'], 1.0, 1.0))
        assert len(runs[0][1]) == 2

    def test_runs_extrude_the_footprint_per_filament(self):
        """Each vertical run of the blend code extrudes the same footprint"""
        runs = list(block_box_runs(self._labels([(0, 0), (1, 0)]), ['CCM'], 1.0, 0.5))
        assert [(code, boxes[0][2]) for code, boxes, _ in runs] == [('C', (0.0, 1.0)), ('M', (1.0, 1.5))]
        assert {boxes[0][:2] for _, boxes, _ in runs} == {((0.0, 2.0), (0.0, 1.0))}

    def test_ungreedy_meshing_boxes_every_cell(self):
        """Without greedy meshing every cell is its own box"""
        runs = list(block_box_runs(self._labels([(0, 0), (1, 0)]), ['C'], 1.0, 1.0, use_greedy_meshing=False))
        assert sorted(runs[0][1]) == [((0.0, 1.0), (0.0, 1.0), (0.0, 1.0)), ((1.0, 2.0), (0.0, 1.0), (0.0, 1.0))]

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
