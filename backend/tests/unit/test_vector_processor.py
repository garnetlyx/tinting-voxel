"""
Unit tests for Vector-based Processing Mode

Tests the contour extraction and simplification algorithms
for generating vector-based STL files.
"""
import numpy as np

from services.vector_processor import (
    VectorProcessorConfig,
    extract_regions_from_mask,
    finalize_vector_partition,
    contour_to_polygon,
    extract_color_mask,
    filter_small_contours,
    find_contours,
    render_region_mask,
    simplify_contour,
)


def test_final_vector_partition_assigns_every_pixel_once():
    results = [
        {'color': (255, 0, 0), 'regions': [
            {'outer': [(0, 0), (3, 0), (3, 7), (0, 7)], 'holes': []},
        ]},
        {'color': (0, 0, 255), 'regions': [
            {'outer': [(7, 0), (11, 0), (11, 7), (7, 7)], 'holes': []},
        ]},
    ]
    labels = finalize_vector_partition(results, {'width': 12, 'height': 8}, 0.2, None)
    assert labels.shape == (8, 12)
    assert set(np.unique(labels)) == {0, 1}
    assert np.all(labels[:, :4] == 0)
    assert np.all(labels[:, 7:] == 1)


def test_final_vector_partition_fills_sub_nozzle_hole():
    result = {'color': (0, 0, 0), 'regions': [
        {
            'outer': [(0, 0), (11, 0), (11, 11), (0, 11)],
            'holes': [[(5, 5), (6, 5), (6, 6), (5, 6)]],
        },
    ]}
    labels = finalize_vector_partition([result], {'width': 12, 'height': 12}, 0.1575, 0.42)
    assert np.all(labels == 0)


def test_final_vector_partition_does_not_leave_one_pixel_stroke():
    results = [
        {'color': (255, 255, 255), 'regions': [
            {'outer': [(0, 0), (23, 0), (23, 19), (0, 19)], 'holes': []},
        ]},
        {'color': (0, 0, 0), 'regions': [
            {'outer': [(5, 2), (5.3, 2), (5.3, 17), (5, 17)], 'holes': []},
        ]},
    ]
    labels = finalize_vector_partition(results, {'width': 24, 'height': 20}, 0.1575, 0.42)
    stroke_width = int(np.count_nonzero(labels[10] == 1))
    assert stroke_width == 0 or stroke_width >= 3


def test_final_vector_partition_widens_bridge_between_large_regions():
    results = [
        {'color': (255, 255, 255), 'regions': [
            {'outer': [(0, 0), (29, 0), (29, 24), (0, 24)], 'holes': []},
        ]},
        {'color': (0, 0, 0), 'regions': [
            {'outer': [(2, 2), (8, 2), (8, 22), (2, 22)], 'holes': []},
            {'outer': [(21, 2), (27, 2), (27, 22), (21, 22)], 'holes': []},
            {'outer': [(8, 12), (21, 12), (21, 12.3), (8, 12.3)], 'holes': []},
        ]},
    ]
    labels = finalize_vector_partition(results, {'width': 30, 'height': 25}, 0.1, 0.42)
    bridge_width = int(np.count_nonzero(labels[:, 15] == 1))
    assert bridge_width == 0 or bridge_width >= 5


class TestVectorProcessorConfig:
    """Tests for VectorProcessorConfig dataclass"""

    def test_default_values(self):
        """Default config should have sensible values"""
        config = VectorProcessorConfig()
        assert config.epsilon >= 0.5
        assert config.min_area >= 10
        assert config.num_colors > 0

    def test_custom_values(self):
        """Custom values should be preserved"""
        config = VectorProcessorConfig(
            epsilon=5.0,
            min_area=200,
            num_colors=16,
            pixel_size=0.2,
            detail_size=0.4,
        )
        assert config.epsilon == 5.0
        assert config.min_area == 200
        assert config.num_colors == 16
        assert config.pixel_size == 0.2
        assert config.detail_size == 0.4


class TestExtractColorMask:
    """Tests for extracting color mask from image"""

    def test_single_color_image(self):
        """Single color image should produce full mask"""
        # Create 10x10 red image
        image = np.full((10, 10, 3), [255, 0, 0], dtype=np.uint8)
        mask = extract_color_mask(image, color=(255, 0, 0))
        assert mask.shape == (10, 10)
        assert mask.all()  # All pixels should be True

    def test_no_matching_color(self):
        """Image with no matching color should produce empty mask"""
        image = np.full((10, 10, 3), [255, 0, 0], dtype=np.uint8)
        mask = extract_color_mask(image, color=(0, 255, 0))  # Green
        assert not mask.any()  # No pixels should match

    def test_partial_match(self):
        """Image with partial color match"""
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[0:5, :] = [255, 0, 0]  # Top half red
        image[5:10, :] = [0, 255, 0]  # Bottom half green

        red_mask = extract_color_mask(image, color=(255, 0, 0))
        assert red_mask[:5, :].all()  # Top half
        assert not red_mask[5:, :].any()  # Bottom half

    def test_tolerance_matching(self):
        """Color matching should work with small tolerance"""
        image = np.full((10, 10, 3), [250, 5, 5], dtype=np.uint8)  # Almost red
        mask = extract_color_mask(image, color=(255, 0, 0), tolerance=10)
        assert mask.all()


class TestFindContours:
    """Tests for finding contours in a binary mask"""

    def test_empty_mask(self):
        """Empty mask should return no contours"""
        mask = np.zeros((10, 10), dtype=np.uint8)
        contours = find_contours(mask)
        assert len(contours) == 0

    def test_single_rectangle(self):
        """Single filled rectangle should return one contour"""
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[5:15, 5:15] = 255  # 10x10 filled rectangle
        contours = find_contours(mask)
        assert len(contours) >= 1

    def test_multiple_regions(self):
        """Multiple separate regions should return multiple contours"""
        mask = np.zeros((30, 30), dtype=np.uint8)
        mask[2:8, 2:8] = 255    # Region 1
        mask[12:18, 12:18] = 255  # Region 2
        mask[22:28, 22:28] = 255  # Region 3
        contours = find_contours(mask)
        assert len(contours) == 3


class TestSimplifyContour:
    """Tests for Douglas-Peucker contour simplification"""

    def test_already_simple_contour(self):
        """Simple contour should remain unchanged with low epsilon"""
        # Simple triangle
        contour = np.array([[0, 0], [10, 0], [5, 10]], dtype=np.float32)
        simplified = simplify_contour(contour, epsilon=0.1)
        assert len(simplified) == 3

    def test_simplification_reduces_points(self):
        """High epsilon should reduce point count"""
        # Circle approximation with many points
        angles = np.linspace(0, 2 * np.pi, 100)
        contour = np.column_stack([
            50 + 40 * np.cos(angles),
            50 + 40 * np.sin(angles)
        ]).astype(np.float32)

        simplified = simplify_contour(contour, epsilon=5.0)
        assert len(simplified) < len(contour)

    def test_higher_epsilon_more_simplification(self):
        """Higher epsilon should produce fewer points"""
        angles = np.linspace(0, 2 * np.pi, 100)
        contour = np.column_stack([
            50 + 40 * np.cos(angles),
            50 + 40 * np.sin(angles)
        ]).astype(np.float32)

        simplified_low = simplify_contour(contour, epsilon=1.0)
        simplified_high = simplify_contour(contour, epsilon=10.0)
        assert len(simplified_high) <= len(simplified_low)


class TestFilterSmallContours:
    """Tests for filtering contours by area"""

    def test_empty_list(self):
        """Empty contour list should return empty"""
        result = filter_small_contours([], min_area=100)
        assert len(result) == 0

    def test_all_contours_kept(self):
        """Large contours should be kept"""
        # Large square contour
        large = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        result = filter_small_contours([large], min_area=100)
        assert len(result) == 1

    def test_small_contours_filtered(self):
        """Small contours should be removed"""
        # Small square contour (area = 4)
        small = np.array([[0, 0], [2, 0], [2, 2], [0, 2]], dtype=np.float32)
        result = filter_small_contours([small], min_area=100)
        assert len(result) == 0

    def test_mixed_sizes(self):
        """Only large enough contours should pass"""
        large = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        small = np.array([[0, 0], [2, 0], [2, 2], [0, 2]], dtype=np.float32)
        result = filter_small_contours([large, small], min_area=100)
        assert len(result) == 1


class TestContourToPolygon:
    """Tests for converting contour to polygon format"""

    def test_simple_contour(self):
        """Simple contour should convert to polygon"""
        contour = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
        polygon = contour_to_polygon(contour, pixel_size=1.0)
        assert len(polygon) == 4
        # Check structure: list of (x, y) tuples
        assert all(len(p) == 2 for p in polygon)

    def test_pixel_size_scaling(self):
        """Pixel size should scale coordinates"""
        contour = np.array([[0, 0], [10, 0], [10, 10]], dtype=np.float32)
        polygon = contour_to_polygon(contour, pixel_size=0.5)

        # Expected: coordinates scaled by 0.5
        assert polygon[0] == (0.0, 0.0)
        assert polygon[1] == (5.0, 0.0)
        assert polygon[2] == (5.0, 5.0)


class TestVectorProcessorIntegration:
    """Integration tests for the full vector processing pipeline"""

    def test_full_pipeline_simple_image(self):
        """Full pipeline should work on simple image"""
        from services.vector_processor import process_image_vector

        # Create simple 2-color image
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        image[10:40, 10:40] = [255, 0, 0]  # Red square

        config = VectorProcessorConfig(epsilon=2.0, min_area=50, num_colors=2)
        result = process_image_vector(image, config)

        # Should have at least one color region
        assert len(result) >= 1
        # Each result should have color and contours
        for color_data in result:
            assert 'color' in color_data
            assert 'regions' in color_data

    def test_vector_mode_produces_fewer_points_than_pixels(self):
        """Vector mode should produce significantly fewer points than pixel count"""
        from services.vector_processor import process_image_vector

        # Create image with simple shape
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[20:80, 20:80] = [255, 0, 0]  # 60x60 red square = 3600 pixels

        config = VectorProcessorConfig(epsilon=2.0, min_area=50, num_colors=2)
        result = process_image_vector(image, config)

        # Count total polygon points
        total_points = sum(
            len(polygon)
            for color_data in result
            for region in color_data['regions']
            for polygon in [region['outer'], *region['holes']]
        )

        # Should be much less than 3600 pixels
        assert total_points < 100  # A simplified square should have ~4-8 points

    def test_svg_cleanup_removes_tiny_island(self):
        """detail_size removes a sub-threshold island before contour extraction."""
        from services.vector_processor import process_image_vector

        image = np.full((5, 5, 3), [255, 0, 0], dtype=np.uint8)
        image[2, 2] = [0, 0, 255]

        config = VectorProcessorConfig(
            epsilon=1.0,
            min_area=1,
            num_colors=2,
            pixel_size=0.2,
            detail_size=0.4,
        )
        result = process_image_vector(image, config)

        result_colors = {tuple(item['color']) for item in result}
        assert (0, 0, 255) not in result_colors
        assert (255, 0, 0) in result_colors

    def test_svg_cleanup_keeps_threshold_sized_island(self):
        """A component at the minimum threshold is preserved."""
        from services.vector_processor import process_image_vector

        image = np.full((7, 7, 3), [255, 0, 0], dtype=np.uint8)
        image[2:5, 2:5] = [0, 0, 255]

        config = VectorProcessorConfig(
            epsilon=1.0,
            min_area=1,
            num_colors=2,
            pixel_size=0.2,
            detail_size=0.4,
        )
        result = process_image_vector(image, config)

        result_colors = {tuple(item['color']) for item in result}
        assert (0, 0, 255) in result_colors

    def test_extract_regions_preserves_hole_geometry(self):
        """A donut mask should become one region with one hole."""
        mask = np.zeros((7, 7), dtype=np.uint8)
        mask[1:6, 1:6] = 255
        mask[3, 3] = 0

        regions = extract_regions_from_mask(mask, epsilon=0.1, min_area=1)

        assert len(regions) == 1
        assert len(regions[0]['holes']) == 1

        rendered = render_region_mask(regions, width=7, height=7)
        assert rendered[2, 2]
        assert not rendered[3, 3]


# ---------------------------------------------------------------------------
# Fix 1: hue-priority LCh clustering
# ---------------------------------------------------------------------------

class TestHuePriorityQuantization:
    """quantize_colors_with_labels should separate hues before lightness."""

    def test_same_image_quantizes_identically_on_every_call(self):
        """Search previews must match applying the same settings later."""
        from services.vector_processor import quantize_colors_with_labels

        image = np.random.default_rng(3).integers(0, 256, (48, 64, 3), dtype=np.uint8)
        first = quantize_colors_with_labels(image, 12)
        for _ in range(3):
            again = quantize_colors_with_labels(image, 12)
            assert np.array_equal(again[1], first[1])
            assert again[2] == first[2]

    def test_same_hue_different_lightness_same_cluster(self):
        """
        Two blues with the same hue angle but different lightness should land
        in the same cluster when there are more hue regions than clusters.

        This is the real-world scenario: an image has 7 distinct color regions
        but the user requests 6 clusters. The two blues share the same hue
        (h ≈ -80° in CIELAB) but differ in lightness (L=62 vs L=25). Plain
        CIELAB k-means can split them because the L difference is large; the
        hue-weighted LCh feature space keeps them together by down-weighting L.

        Colors used:
          cornflower (100,149,237): L=62, C=50, h=-80°
          dark cornflower (40,59,94): L=25, C=23, h=-80°  ← same hue, darker
        """
        from services.vector_processor import quantize_colors_with_labels

        H, W = 70, 60
        image = np.zeros((H, W, 3), dtype=np.uint8)

        # 7 hue regions (10 rows each): 5 distinct hues + 2 same-hue blue variants
        image[0:10, :] = (220, 30, 30)    # Red       h≈+36°
        image[10:20, :] = (30, 180, 30)   # Green     h≈+137°
        image[20:30, :] = (100, 149, 237) # Light blue (cornflower) h≈-80°
        image[30:40, :] = (40, 59, 94)    # Dark cornflower         h≈-80°
        image[40:50, :] = (220, 200, 30)  # Yellow    h≈+97°
        image[50:60, :] = (10, 10, 10)    # Black     (neutral)
        image[60:70, :] = (200, 100, 200) # Magenta   h≈-30°

        # Request 6 clusters for 7 regions → the two same-hue blues must merge
        _, label_grid, colors = quantize_colors_with_labels(image, num_colors=6)

        light_blue_label = int(label_grid[25, 30])
        dark_blue_label = int(label_grid[35, 30])

        assert light_blue_label == dark_blue_label, (
            f"Same-hue blues (light cluster {light_blue_label}, dark cluster "
            f"{dark_blue_label}) should merge when clusters < hue regions. "
            f"Palette: {colors}"
        )

    def test_different_hues_different_clusters(self):
        """Red and blue must always be in different clusters."""
        from services.vector_processor import quantize_colors_with_labels

        H, W = 20, 40
        image = np.zeros((H, W, 3), dtype=np.uint8)
        image[:, :20] = (200, 20, 20)   # Red
        image[:, 20:] = (20, 20, 200)   # Blue

        _, label_grid, _ = quantize_colors_with_labels(image, num_colors=2)

        red_label = int(label_grid[10, 5])
        blue_label = int(label_grid[10, 35])

        assert red_label != blue_label, (
            "Red and blue must be assigned to different clusters"
        )

    def test_neutral_colors_still_separate(self):
        """Black and white (neutral, C≈0) must still be in different clusters."""
        from services.vector_processor import quantize_colors_with_labels

        H, W = 20, 40
        image = np.zeros((H, W, 3), dtype=np.uint8)
        image[:, :20] = (5, 5, 5)       # Black
        image[:, 20:] = (250, 250, 250) # White

        _, label_grid, _ = quantize_colors_with_labels(image, num_colors=2)

        black_label = int(label_grid[10, 5])
        white_label = int(label_grid[10, 35])

        assert black_label != white_label, (
            "Black and white must be assigned to different clusters"
        )


def test_final_svg_partition_holds_the_detail_width():
    from PIL import Image, ImageDraw
    from services.raster_cleanup import unprintable_pixels
    from services.vector_processor import (
        VectorProcessorConfig, finalize_vector_partition, process_image_vector_with_preview,
    )

    image = Image.new('RGB', (240, 180), (200, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 120, 180), fill=(40, 70, 200))
    for offset in range(-180, 240, 23):
        draw.line((offset, 0, offset + 180, 180), fill=(10, 10, 10), width=1)
    pixel_size = 200 / 1270
    config = VectorProcessorConfig(
        epsilon=1.0, min_area=1, num_colors=4, pixel_size=pixel_size, detail_size=0.42,
    )
    results, _ = process_image_vector_with_preview(np.array(image), config)
    labels = finalize_vector_partition(results, {'width': 240, 'height': 180}, pixel_size, 0.42)

    assert unprintable_pixels(labels, 0.42 / pixel_size / 2).sum() <= 0.001 * labels.size
