"""
Unit tests for image processing service, including large image handling.
"""
from io import BytesIO

import pytest
from PIL import Image

from services.image_processor import (
    MAX_PROCESSING_DIMENSION,
    _downscale_if_needed,
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
