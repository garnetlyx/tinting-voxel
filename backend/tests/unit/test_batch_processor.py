"""
Unit tests for batch processing service.
"""
from io import BytesIO

import pytest
from PIL import Image

from services.batch_processor import (
    MAX_BATCH_SIZE,
    generate_batch_stl_zip,
    process_batch_images,
)


def _create_test_image(width=4, height=4, color=(255, 0, 0)) -> bytes:
    """Create a small test PNG image in memory."""
    img = Image.new('RGB', (width, height), color)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class TestProcessBatchImages:
    """Tests for process_batch_images."""

    def test_single_image_success(self):
        """Process a single valid image."""
        files = [('test.png', _create_test_image())]
        result = process_batch_images(files)

        assert result['totalImages'] == 1
        assert result['successCount'] == 1
        assert result['errorCount'] == 0
        assert len(result['results']) == 1
        assert result['results'][0]['status'] == 'success'
        assert result['results'][0]['filename'] == 'test.png'
        assert result['results'][0]['colorBlocks'] is not None
        assert result['results'][0]['imageDimensions'] is not None

    def test_multiple_images_success(self):
        """Process multiple valid images."""
        files = [
            ('red.png', _create_test_image(color=(255, 0, 0))),
            ('green.png', _create_test_image(color=(0, 255, 0))),
            ('blue.png', _create_test_image(color=(0, 0, 255))),
        ]
        result = process_batch_images(files)

        assert result['totalImages'] == 3
        assert result['successCount'] == 3
        assert result['errorCount'] == 0

    def test_invalid_image_produces_error_result(self):
        """Invalid file content produces an error result."""
        files = [('bad.png', b'not an image')]
        result = process_batch_images(files)

        assert result['totalImages'] == 1
        assert result['successCount'] == 0
        assert result['errorCount'] == 1
        assert result['results'][0]['status'] == 'error'
        assert result['results'][0]['error'] is not None

    def test_mixed_valid_and_invalid(self):
        """Mix of valid and invalid images."""
        files = [
            ('good.png', _create_test_image()),
            ('bad.png', b'not an image'),
            ('good2.png', _create_test_image(color=(0, 255, 0))),
        ]
        result = process_batch_images(files)

        assert result['totalImages'] == 3
        assert result['successCount'] == 2
        assert result['errorCount'] == 1
        assert result['results'][0]['status'] == 'success'
        assert result['results'][1]['status'] == 'error'
        assert result['results'][2]['status'] == 'success'

    def test_empty_batch_raises_value_error(self):
        """Empty batch raises ValueError."""
        with pytest.raises(ValueError, match="No images provided"):
            process_batch_images([])

    def test_exceeds_max_batch_size(self):
        """Batch exceeding MAX_BATCH_SIZE raises ValueError."""
        files = [(f'img{i}.png', _create_test_image()) for i in range(MAX_BATCH_SIZE + 1)]
        with pytest.raises(ValueError, match="exceeds maximum"):
            process_batch_images(files)

    def test_custom_parameters(self):
        """Custom max_colors and color_threshold are respected."""
        files = [('test.png', _create_test_image())]
        result = process_batch_images(
            files,
            max_colors=3,
            color_threshold=100,
            pixel_size=0.1,
        )
        assert result['successCount'] == 1

    def test_max_batch_size_exactly(self):
        """Exactly MAX_BATCH_SIZE images is allowed."""
        files = [(f'img{i}.png', _create_test_image()) for i in range(MAX_BATCH_SIZE)]
        result = process_batch_images(files)
        assert result['totalImages'] == MAX_BATCH_SIZE
        assert result['successCount'] == MAX_BATCH_SIZE


class TestGenerateBatchStlZip:
    """Tests for generate_batch_stl_zip."""

    def test_generates_zip_from_successful_results(self):
        """Generate ZIP from batch results."""
        files = [
            ('red.png', _create_test_image(color=(255, 0, 0))),
            ('blue.png', _create_test_image(color=(0, 0, 255))),
        ]
        batch = process_batch_images(files)

        zip_bytes = generate_batch_stl_zip(
            batch_results=batch['results'],
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
        )

        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0
        # Verify it's a valid ZIP (PK magic bytes)
        assert zip_bytes[:2] == b'PK'

    def test_zip_contains_per_image_entries(self):
        """ZIP contains one entry per successful image."""
        import zipfile
        from io import BytesIO

        files = [
            ('alpha.png', _create_test_image(color=(255, 0, 0))),
            ('beta.png', _create_test_image(color=(0, 255, 0))),
        ]
        batch = process_batch_images(files)

        zip_bytes = generate_batch_stl_zip(
            batch_results=batch['results'],
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
        )

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert 'alpha.zip' in names
            assert 'beta.zip' in names

    def test_skips_error_results(self):
        """Error results are skipped in STL generation."""
        import zipfile
        from io import BytesIO

        files = [
            ('good.png', _create_test_image()),
            ('bad.png', b'not an image'),
        ]
        batch = process_batch_images(files)

        zip_bytes = generate_batch_stl_zip(
            batch_results=batch['results'],
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
        )

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert 'good.zip' in names
            assert 'bad.zip' not in names

    def test_no_successful_results_raises_error(self):
        """ValueError when all results are errors."""
        results = [{'filename': 'bad.png', 'status': 'error', 'error': 'fail'}]

        with pytest.raises(ValueError, match="No successful"):
            generate_batch_stl_zip(
                batch_results=results,
                layer_height=0.08,
                pixel_size=0.08,
                layer_count=4,
            )

    def test_custom_colors(self):
        """Custom Colors instance is used."""
        from core.blend_color import Colors
        from core.color_config import BAMBU_CMYW_PHASE6_PRESET

        files = [('test.png', _create_test_image())]
        batch = process_batch_images(files)
        colors = Colors.from_configs(BAMBU_CMYW_PHASE6_PRESET)

        zip_bytes = generate_batch_stl_zip(
            batch_results=batch['results'],
            layer_height=0.08,
            pixel_size=0.08,
            layer_count=4,
            colors=colors,
        )

        assert isinstance(zip_bytes, bytes)
        assert len(zip_bytes) > 0
