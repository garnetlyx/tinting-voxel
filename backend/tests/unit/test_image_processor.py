"""
Unit tests for image processing service, including large image handling.
"""
from io import BytesIO

import pytest
from PIL import Image

from services.image_processor import (
    MAX_PROCESSING_DIMENSION,
    _downscale_if_needed,
    build_simulated_print_preview,
    merge_small_pixels_to_neighbors,
    process_image,
)


def _create_image_bytes(width, height, color=(255, 0, 0), fmt='PNG'):
    """Create an image of given size and return as bytes."""
    img = Image.new('RGB', (width, height), color)
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestDownscaleIfNeeded:
    """Tests for _downscale_if_needed."""

    def test_small_image_unchanged(self):
        """Image smaller than max_dim is not modified."""
        img = Image.new('RGB', (100, 100))
        result = _downscale_if_needed(img, 1024)
        assert result.size == (100, 100)

    def test_exactly_max_dim_unchanged(self):
        """Image exactly at max_dim is not modified."""
        img = Image.new('RGB', (1024, 512))
        result = _downscale_if_needed(img, 1024)
        assert result.size == (1024, 512)

    def test_large_width_downscaled(self):
        """Image with width > max_dim is downscaled."""
        img = Image.new('RGB', (2048, 1024))
        result = _downscale_if_needed(img, 1024)
        assert result.size[0] == 1024
        assert result.size[1] == 512

    def test_large_height_downscaled(self):
        """Image with height > max_dim is downscaled."""
        img = Image.new('RGB', (512, 2048))
        result = _downscale_if_needed(img, 1024)
        assert result.size[0] == 256
        assert result.size[1] == 1024

    def test_aspect_ratio_preserved(self):
        """Downscaling preserves aspect ratio."""
        img = Image.new('RGB', (3000, 2000))
        result = _downscale_if_needed(img, 1024)
        original_ratio = 3000 / 2000
        new_ratio = result.size[0] / result.size[1]
        assert abs(original_ratio - new_ratio) < 0.01


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
            image_dimensions={'width': 2, 'height': 2},
            white_backing_layers=0,
        )

        assert result['processedImage'].startswith('data:image/png;base64,')
        assert len(result['mappedBlockColors']) == len(color_blocks)
        assert sum(entry['pixelCount'] for entry in result['mappedBlendPalette']) == 4
        assert result['mappedBlendPalette'][0]['pixelPercent'] >= result['mappedBlendPalette'][1]['pixelPercent']
        assert result['printStack']['whiteBackingLayers'] == 0
        assert result['printStack']['totalLayerCount'] == 4

    def test_small_components_merge_without_global_scaling(self):
        """detail_size merges local components instead of enlarging the full image."""
        color_blocks = [
            {'r': 255, 'g': 0, 'b': 0, 'hex': '#ff0000', 'count': 1, 'pixels': [{'x': 0, 'y': 0}]},
            {'r': 250, 'g': 10, 'b': 10, 'hex': '#fa0a0a', 'count': 1, 'pixels': [{'x': 1, 'y': 0}]},
            {
                'r': 0, 'g': 0, 'b': 255, 'hex': '#0000ff', 'count': 4,
                'pixels': [{'x': 2, 'y': 0}, {'x': 3, 'y': 0}, {'x': 4, 'y': 0}, {'x': 5, 'y': 0}],
            },
        ]

        merged = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            width=6,
            height=1,
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert merged[0]['count'] == 6

    def test_single_component_image_is_preserved(self):
        """A single-region image has no valid merge target and remains unchanged."""
        color_blocks = [
            {'r': 255, 'g': 0, 'b': 0, 'hex': '#ff0000', 'count': 1, 'pixels': [{'x': 0, 'y': 0}]},
        ]

        merged = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            width=1,
            height=1,
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert merged[0]['count'] == 1

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

        merged = merge_small_pixels_to_neighbors(
            color_blocks=color_blocks,
            width=3,
            height=3,
            pixel_size=0.2,
            detail_size=0.4,
        )

        assert len(merged) == 1
        assert merged[0]['count'] == 9
