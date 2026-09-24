"""
Unit tests for image processing service, including large image handling.
"""
import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from config.settings import settings
from services.image_processor import (
    MAX_PROCESSING_DIMENSION,
    build_simulated_print_preview,
    build_vector_simulated_preview,
    merge_small_pixels_to_neighbors,
    process_image,
    resample_to_model_grid,
)
from tests.label_maps import labels_from_blocks


def _create_image_bytes(width, height, color=(255, 0, 0), fmt='PNG'):
    """Create an image of given size and return as bytes."""
    img = Image.new('RGB', (width, height), color)
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _decode_data_url_image(data_url: str) -> np.ndarray:
    """Decode a PNG data URL into an RGB numpy array."""
    encoded = data_url.split(",", 1)[1]
    image_bytes = base64.b64decode(encoded)
    return np.array(Image.open(BytesIO(image_bytes)).convert("RGB"))


class TestModelGrid:
    """The model grid resolution policy (resample_to_model_grid)."""

    def test_image_within_the_limits_keeps_its_pitch(self):
        img = Image.new('RGB', (100, 100))
        result, pitch = resample_to_model_grid(img, 0.05, 0.42)
        assert result.size == (100, 100)
        assert pitch == 0.05

    def test_cell_budget_bounds_the_grid(self, monkeypatch):
        monkeypatch.setattr(settings, "max_model_cells", 10_000)
        img = Image.new('RGB', (400, 300))
        result, pitch = resample_to_model_grid(img, 1.0, None)
        assert result.size[0] * result.size[1] <= 10_000
        assert max(result.size) * pitch == pytest.approx(400.0)

    def test_side_length_is_capped(self):
        img = Image.new('RGB', (MAX_PROCESSING_DIMENSION + 500, 10))
        result, _ = resample_to_model_grid(img, 1.0, None)
        assert max(result.size) <= MAX_PROCESSING_DIMENSION

    def test_forced_pitch_below_one_detail_snaps_to_the_detail(self, monkeypatch):
        # The cell budget alone would give 0.3 mm cells; with 0.42 mm detail
        # the grid uses whole detail-width cells instead.
        monkeypatch.setattr(settings, "max_model_cells", 10_000)
        img = Image.new('RGB', (300, 300))
        result, pitch = resample_to_model_grid(img, 0.1, 0.42)
        assert pitch >= 0.42
        assert result.size == (71, 71)

    def test_native_pixel_art_is_not_resampled(self):
        # 0.3 mm pixels with 0.42 mm detail stay crisp when no limit forces resampling.
        img = Image.new('RGB', (64, 64))
        result, pitch = resample_to_model_grid(img, 0.3, 0.42)
        assert result.size == (64, 64)
        assert pitch == 0.3

    def test_resampled_grid_passes_through_unchanged(self, monkeypatch):
        monkeypatch.setattr(settings, "max_model_cells", 100_000)
        img = Image.new('RGB', (2000, 1500))
        once, pitch = resample_to_model_grid(img, 0.05, 0.42)
        twice, again = resample_to_model_grid(once, pitch, 0.42)
        assert twice.size == once.size
        assert again == pitch

    @pytest.mark.parametrize("size", [(1, 10000), (10000, 1)])
    def test_extreme_aspect_ratio_keeps_every_side(self, size):
        result, _ = resample_to_model_grid(Image.new('RGB', size), 1.0, None)
        assert min(result.size) >= 1


class TestProcessImageLargeHandling:
    """Tests for process_image with large images."""

    def test_small_image_processes(self):
        """Small image processes correctly."""
        img_bytes = _create_image_bytes(4, 4, color=(255, 0, 0))
        result = process_image(img_bytes)
        assert result['imageDimensions']['width'] == 4
        assert result['imageDimensions']['height'] == 4
        assert len(result['colorBlocks']) > 0

    def test_large_image_auto_downscaled(self):
        """Large image is automatically downscaled."""
        # Create an image larger than MAX_PROCESSING_DIMENSION
        large_dim = MAX_PROCESSING_DIMENSION + 500
        img_bytes = _create_image_bytes(large_dim, large_dim, color=(0, 255, 0))
        result = process_image(img_bytes)

        # Dimensions should be <= MAX_PROCESSING_DIMENSION
        assert result['imageDimensions']['width'] <= MAX_PROCESSING_DIMENSION
        assert result['imageDimensions']['height'] <= MAX_PROCESSING_DIMENSION

    def test_process_returns_valid_preview(self):
        """Process returns a valid base64 PNG preview."""
        img_bytes = _create_image_bytes(8, 8, color=(0, 0, 255))
        result = process_image(img_bytes)
        assert result['processedImage'].startswith('data:image/png;base64,')
        assert result['segmentationImage'].startswith('data:image/png;base64,')
        assert isinstance(result['mappedBlockColors'], list)
        assert isinstance(result['mappedBlendPalette'], list)
        assert len(result['mappedBlendPalette']) > 0

    def test_process_with_multiple_colors(self):
        """Process handles image with multiple colors."""
        img = Image.new('RGB', (4, 4))
        pixels = img.load()
        pixels[0, 0] = (255, 0, 0)
        pixels[1, 0] = (0, 255, 0)
        pixels[2, 0] = (0, 0, 255)
        pixels[3, 0] = (255, 255, 255)
        for y in range(1, 4):
            for x in range(4):
                pixels[x, y] = pixels[x, 0]

        buf = BytesIO()
        img.save(buf, format='PNG')

        result = process_image(buf.getvalue(), max_colors=4)
        assert len(result['colorBlocks']) <= 4
        assert len(result['mappedBlockColors']) == len(result['colorBlocks'])
        assert len(result['mappedBlendPalette']) == len(result['colorBlocks'])

    def test_simulated_preview_palette_counts_match_pixels(self):
        """Mapped blend palette accounts for every pixel in the image."""
        color_blocks = [
            {
                'r': 255,
                'g': 0,
                'b': 0,
                'hex': '#ff0000',
                'count': 3,
                'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 0, 'y': 1}],
            },
            {
                'r': 0,
                'g': 0,
                'b': 255,
                'hex': '#0000ff',
                'count': 1,
                'pixels': [{'x': 1, 'y': 1}],
            },
        ]

        result = build_simulated_print_preview(
            color_blocks=color_blocks,
            labels=labels_from_blocks(color_blocks, 2, 2),
            white_backing_layers=0,
        )

        assert result['processedImage'].startswith('data:image/png;base64,')
        assert len(result['mappedBlockColors']) == len(color_blocks)
        assert sum(entry['pixelCount'] for entry in result['mappedBlendPalette']) == 4
        assert result['mappedBlendPalette'][0]['pixelPercent'] >= result['mappedBlendPalette'][1]['pixelPercent']
        assert result['printStack']['whiteBackingLayers'] == 0
        assert result['printStack']['totalLayerCount'] == 4

    def test_vector_simulated_preview_returns_palette_and_image(self):
        """SVG preview uses printable blends and reports palette coverage."""
        quantized = np.array(
            [
                [[255, 0, 0], [255, 0, 0]],
                [[0, 0, 255], [0, 0, 255]],
            ],
            dtype=np.uint8,
        )
        vector_results = [
            {
                "color": (255, 0, 0),
                "regions": [{"outer": [(0, 0), (1, 0), (1, 1), (0, 1)], "holes": []}],
                "pixel_count": 2,
                "polygon_points": 4,
            },
            {
                "color": (0, 0, 255),
                "regions": [{"outer": [(0, 1), (1, 1), (1, 2), (0, 2)], "holes": []}],
                "pixel_count": 2,
                "polygon_points": 4,
            },
        ]

        result = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            pixel_size=0.42,
            detail_size=None,
            white_backing_layers=0,
        )

        assert result['processedImage'].startswith('data:image/png;base64,')
        assert len(result['mappedBlendPalette']) == 2
        assert sum(entry['pixelCount'] for entry in result['mappedBlendPalette']) == 4
        assert result['printStack']['whiteBackingLayers'] == 0

    def test_vector_simulated_preview_uses_final_geometry_not_quantized_pixels(self):
        """The preview fills vector gaps using the final printable partition."""
        quantized = np.array(
            [
                [[0, 255, 0], [0, 255, 0], [0, 255, 0]],
                [[0, 255, 0], [0, 255, 0], [0, 255, 0]],
                [[0, 255, 0], [0, 255, 0], [0, 255, 0]],
            ],
            dtype=np.uint8,
        )
        vector_results = [
            {
                "color": (255, 0, 0),
                "regions": [{
                    "outer": [(0, 0), (2, 0), (2, 2), (0, 2)],
                    "holes": [[(1, 1), (2, 1), (2, 2), (1, 2)]],
                }],
                "pixel_count": 8,
                "polygon_points": 8,
            }
        ]

        result = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            pixel_size=0.42,
            detail_size=None,
            white_backing_layers=0,
        )

        preview = _decode_data_url_image(result['processedImage'])
        hole_pixel = tuple(int(v) for v in preview[1, 1])
        # Quantized green deliberately disagrees with the red printable
        # region. A gap must use the exported region's blend, not the
        # quantized-image background blend.
        assert hole_pixel == tuple(int(v) for v in preview[0, 0])

    def test_vector_preview_omits_regions_removed_by_print_cleanup(self):
        """The response palette contains only material regions still printed."""
        quantized = np.zeros((20, 20, 3), dtype=np.uint8)
        vector_results = [
            {
                'color': (0, 0, 255),
                'regions': [{'outer': [(0, 0), (19, 0), (19, 19), (0, 19)], 'holes': []}],
            },
            {
                'color': (255, 0, 0),
                'regions': [{'outer': [(9, 9), (10, 9), (10, 10), (9, 10)], 'holes': []}],
            },
        ]
        result = build_vector_simulated_preview(
            quantized_image=quantized,
            vector_results=vector_results,
            pixel_size=0.1,
            detail_size=0.9,
            white_backing_layers=0,
        )

        palette = result['mappedBlendPalette']
        assert len(palette) == 1
        assert palette[0]['pixelCount'] == 400
        assert _decode_data_url_image(result['processedImage']).shape == (20, 20, 3)

    def test_small_components_merge_without_global_scaling(self):
        """detail_size merges local components instead of enlarging the full image."""
        color_blocks = [
            {'r': 255, 'g': 0, 'b': 0, 'hex': '#ff0000', 'count': 1, 'pixels': [{'x': 0, 'y': 0}]},
            {'r': 250, 'g': 10, 'b': 10, 'hex': '#fa0a0a', 'count': 1, 'pixels': [{'x': 1, 'y': 0}]},
            {
                'r': 0, 'g': 0, 'b': 255, 'hex': '#0000ff', 'count': 10,
                'pixels': ([{'x': x, 'y': 0} for x in range(2, 6)]
                           + [{'x': x, 'y': 1} for x in range(6)]),
            },
        ]

        merged, labels = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            labels=labels_from_blocks(color_blocks, 6, 2),
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert int((labels == 0).sum()) == 12

    def test_single_component_image_is_preserved(self):
        """A single-region image has no valid merge target and remains unchanged."""
        color_blocks = [
            {
                'r': 255, 'g': 0, 'b': 0, 'hex': '#ff0000', 'count': 4,
                'pixels': [{'x': x, 'y': y} for y in range(2) for x in range(2)],
            },
        ]

        merged, labels = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            labels=labels_from_blocks(color_blocks, 2, 2),
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert int((labels == 0).sum()) == 4

    def test_process_image_widens_a_connector_between_large_regions(self):
        pixels = np.full((40, 50, 3), 255, dtype=np.uint8)
        pixels[10:30, 2:17] = 0
        pixels[10:30, 22:37] = 0
        pixels[20, 17:22] = 0
        image_bytes = BytesIO()
        Image.fromarray(pixels).save(image_bytes, format='PNG')

        result = process_image(
            image_bytes.getvalue(), max_colors=2, color_threshold=0,
            pixel_size=0.1, detail_size=0.42,
        )
        black = next(block for block in result['colorBlocks'] if block['r'] == 0)
        printed = {(point['y'], point['x']) for point in black['pixels']}
        assert all((y, x) in printed for y in range(18, 23) for x in range(17, 22))
        assert result['imageDimensions'] == {'width': 50, 'height': 40}

    def test_tiny_hole_disappears(self):
        """A sub-threshold hole is absorbed into the surrounding region."""
        color_blocks = [
            {
                'r': 255, 'g': 0, 'b': 0, 'hex': '#ff0000', 'count': 8,
                'pixels': [
                    {'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 2, 'y': 0},
                    {'x': 0, 'y': 1}, {'x': 2, 'y': 1},
                    {'x': 0, 'y': 2}, {'x': 1, 'y': 2}, {'x': 2, 'y': 2},
                ],
            },
            {
                'r': 0, 'g': 0, 'b': 255, 'hex': '#0000ff', 'count': 1,
                'pixels': [{'x': 1, 'y': 1}],
            },
        ]

        merged, labels = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            labels=labels_from_blocks(color_blocks, 3, 3),
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert int((labels == 0).sum()) == 9


def _stained_glass_bytes(width=240, height=180):
    """Colored panes separated by thin diagonal and curved lead lines."""
    from PIL import ImageDraw

    image = Image.new('RGB', (width, height), (200, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width // 2, height), fill=(40, 70, 200))
    draw.polygon([(width // 2, 0), (width, 0), (width, height // 2)], fill=(230, 200, 40))
    for offset in range(-height, width, 23):
        draw.line((offset, 0, offset + height, height), fill=(10, 10, 10), width=1)
    for offset in range(0, width + height, 31):
        draw.line((offset, 0, offset - height, height), fill=(15, 15, 15), width=2)
    draw.ellipse((60, 40, 180, 140), outline=(5, 5, 5), width=2)
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.mark.parametrize('pixel_size', [200 / 1270, 0.1])
def test_every_exported_pixel_region_holds_the_detail_width(pixel_size):
    """Thin diagonal lines must leave no sub-detail material in the export grid."""
    from services.raster_cleanup import unprintable_pixels

    result = process_image(
        _stained_glass_bytes(), max_colors=6, color_threshold=30,
        pixel_size=pixel_size, layer_count=4, layer_height=0.08, detail_size=0.42,
    )
    width = result['imageDimensions']['width']
    height = result['imageDimensions']['height']
    labels = np.full((height, width), -1, dtype=np.int32)
    for index, block in enumerate(result['colorBlocks']):
        for pixel in block['pixels']:
            labels[pixel['y'], pixel['x']] = index

    assert np.all(labels >= 0)
    assert unprintable_pixels(labels, 0.42 / pixel_size / 2).sum() <= 0.001 * labels.size
    dark = [index for index, block in enumerate(result['colorBlocks']) if block['r'] + block['g'] + block['b'] < 150]
    assert dark and np.isin(labels, dark).sum() > 0.05 * labels.size


def test_exports_reuse_the_mapping_processing_computed(monkeypatch):
    """The same sources against the same reference matrix map once; the cached
    result goes away with its matrix."""
    import gc

    import services.image_processor as image_processor
    from core.blend_color import Colors
    from core.color_config import get_preset
    from core.color_materials import Color
    from services.stl_generator import map_color_blocks_to_blend_results

    from services.stl_generator import compute_reference_matrices

    colors = Colors.from_configs(get_preset("bambu_cmywk"))
    blocks = [{'r': 200, 'g': 40, 'b': 60}, {'r': 20, 'g': 90, 'b': 180}]
    sources = [(b['r'], b['g'], b['b']) for b in blocks]
    compute_reference_matrices(4, 0.08, colors, n_targets=2, backing_layers=3)  # runs the one-time cost probe
    calls = []
    original = Color.map_to_nearest_color
    monkeypatch.setattr(Color, "map_to_nearest_color", staticmethod(lambda *a: calls.append(1) or original(*a)))

    first = image_processor._map_source_colors_to_blends(sources, colors, 4, 0.08, backing_layers=3)
    second = map_color_blocks_to_blend_results(blocks, 0.08, 4, colors, backing_layers=3)
    assert first == second
    assert len(calls) == 1

    image_processor._mapping_cache.clear()  # entries also leave with their matrix:
    matrix, _ = compute_reference_matrices(4, 0.08, colors, n_targets=2, backing_layers=3)
    image_processor._matrix_mappings(matrix)
    assert id(matrix) in image_processor._mapping_cache
    matrix_id = id(matrix)
    from services.matrix_cache import clear_cache
    clear_cache()
    del matrix
    gc.collect()
    assert matrix_id not in image_processor._mapping_cache
