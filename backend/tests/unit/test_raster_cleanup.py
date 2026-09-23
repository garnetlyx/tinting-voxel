from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from services.mesh_optimizer import generate_optimized_boxes
from services.raster_cleanup import regularize_printable_regions, unprintable_pixels

LOCAL_PHOTO_PIXEL_SIZE = 200 / 1270


def _radius(pixel_size, detail_size=0.42):
    return detail_size / pixel_size / 2


def test_connected_border_network_is_kept_and_widened():
    """A stained-glass network of 1 px lines stays, widened to the detail width."""
    labels = np.zeros((50, 50), dtype=np.int32)
    for index in (10, 25, 40):
        labels[index, :] = 1
        labels[:, index] = 1

    cleaned = regularize_printable_regions(labels, [(200, 200, 200), (0, 0, 0)], 0.1, 0.4)

    assert np.all(cleaned[labels == 1] == 1)
    assert np.all(cleaned[15:21, 15:21] == 0)
    assert not unprintable_pixels(cleaned, _radius(0.1, 0.4)).any()


def test_compact_noise_blob_joins_the_surrounding_material():
    labels = np.zeros((20, 20), dtype=np.int32)
    labels[8:11, 8:11] = 1

    cleaned = regularize_printable_regions(labels, [(200, 200, 200), (0, 0, 0)], 0.1, 0.4)

    assert np.all(cleaned == 0)


def test_noise_joins_its_spatial_neighbour_not_a_distant_label():
    labels = np.zeros((50, 50), dtype=np.int32)
    labels[25:, 25:] = 1
    labels[40:42, 40:42] = 2

    cleaned = regularize_printable_regions(
        labels, [(0, 0, 255), (255, 0, 0), (0, 255, 0)], 0.1, 0.4,
    )

    assert np.all(cleaned[40:42, 40:42] == 1)


def test_noise_on_a_boundary_joins_the_more_similar_color():
    labels = np.zeros((40, 40), dtype=np.int32)
    labels[:, 20:] = 1
    labels[18:22, 18:22] = 2

    cleaned = regularize_printable_regions(
        labels, [(250, 250, 250), (0, 0, 0), (30, 30, 30)], 0.1, 0.42,
    )

    assert np.all(cleaned[labels == 1] == 1)
    assert not np.any(cleaned == 2)
    assert np.count_nonzero(cleaned[18:22, 18:20] == 1) > 0


def test_diagonal_one_pixel_line_is_widened_not_erased():
    labels = np.zeros((80, 80), dtype=np.int32)
    for index in range(10, 70):
        labels[index, index] = 1

    cleaned = regularize_printable_regions(
        labels, [(255, 255, 255), (0, 0, 0)], LOCAL_PHOTO_PIXEL_SIZE, 0.42,
    )

    assert all(cleaned[index, index] == 1 for index in range(12, 68))
    assert not unprintable_pixels(cleaned, _radius(LOCAL_PHOTO_PIXEL_SIZE)).any()


def test_three_pixel_line_already_meets_the_detail_width():
    labels = np.zeros((40, 40), dtype=np.int32)
    labels[18:21, 5:35] = 1

    cleaned = regularize_printable_regions(
        labels, [(255, 255, 255), (0, 0, 0)], LOCAL_PHOTO_PIXEL_SIZE, 0.42,
    )

    assert np.array_equal(cleaned, labels)


def test_random_texture_becomes_printable_everywhere():
    y, x = np.indices((60, 72))
    labels = ((x // 3 + 2 * (y // 4)) % 5).astype(np.int32)
    rng = np.random.default_rng(7)
    labels[rng.integers(0, 60, 200), rng.integers(0, 72, 200)] = rng.integers(0, 5, 200)
    colors = [(255, 0, 0), (0, 0, 255), (0, 255, 0), (255, 255, 0), (0, 0, 0)]

    cleaned = regularize_printable_regions(labels, colors, LOCAL_PHOTO_PIXEL_SIZE, 0.42)

    assert cleaned.shape == labels.shape
    assert unprintable_pixels(cleaned, _radius(LOCAL_PHOTO_PIXEL_SIZE)).sum() <= 0.01 * cleaned.size


def test_pixels_at_least_as_large_as_the_detail_width_are_left_unchanged():
    labels = np.zeros((6, 6), dtype=np.int32)
    labels[2, 2] = 1
    assert np.array_equal(
        regularize_printable_regions(labels, [(0, 0, 0), (255, 255, 255)], 0.42, 0.42), labels,
    )


def test_one_pixel_print_stroke_is_physically_widened_without_rescaling():
    labels = np.zeros((24, 30), dtype=np.int32)
    labels[12, 5:25] = 1
    pixel_size = 200 / 1270
    cleaned = regularize_printable_regions(
        labels, [(200, 200, 200), (10, 10, 10)], pixel_size, 0.42,
    )

    assert cleaned.shape == labels.shape
    assert np.all(cleaned[11:14, 6:24] == 1)
    assert np.all(cleaned[10, 6:24] == 0)
    assert 3 * pixel_size >= 0.42


@pytest.mark.parametrize('width,pixel_size', [(5, 0.157), (7, 0.157), (50, 0.01), (70, 0.01)])
def test_small_hole_cannot_replace_the_surrounding_material(width, pixel_size):
    labels = np.zeros((width, width), dtype=np.int32)
    labels[width // 2:width // 2 + 2, width // 2:width // 2 + 2] = 1
    cleaned = regularize_printable_regions(
        labels, [(220, 220, 220), (10, 10, 10)], pixel_size, 0.42,
    )
    assert np.all(cleaned == 0)


def test_image_smaller_than_selected_print_width_is_rejected():
    labels = np.zeros((10, 70), dtype=np.int32)
    labels[5:7, 35:37] = 1
    with pytest.raises(ValueError, match='shorter side'):
        regularize_printable_regions(
            labels, [(220, 220, 220), (10, 10, 10)], 0.01, 0.42,
        )


def test_thin_bridge_between_printable_regions_gets_real_width():
    labels = np.zeros((40, 50), dtype=np.int32)
    labels[10:30, 2:17] = 1
    labels[10:30, 22:37] = 1
    labels[20, 17:22] = 1

    cleaned = regularize_printable_regions(
        labels, [(255, 255, 255), (0, 0, 0)], 0.1, 0.42,
    )
    assert np.all(cleaned[18:23, 17:22] == 1)
    assert np.all(cleaned[17, 17:22] == 0)
    assert cleaned.shape == labels.shape


def test_real_local-photo_detail_survives_as_printable_export_geometry():
    # Paletted crop from the actual 953x1270 Local-photo source after 10-color,
    # threshold-50 quantization; original coordinates x=912:938, y=10:32.
    image_path = Path(__file__).parents[1] / 'fixtures/images/local-photo_quantized_detail_crop.png'
    source = Image.open(image_path)
    labels = np.asarray(source).astype(np.int32)
    palette = source.getpalette()
    source_colors = [tuple(palette[index * 3:index * 3 + 3]) for index in (0, 5)]
    color_blocks = []
    for index, color in zip((0, 5), source_colors):
        ys, xs = np.where(labels == index)
        color_blocks.append({
            'r': color[0], 'g': color[1], 'b': color[2],
            'count': len(xs),
            'pixels': [{'x': int(x), 'y': int(y)} for y, x in zip(ys, xs)],
        })

    from services.image_processor import merge_small_pixels_to_neighbors

    pixel_size = 200 / 1270
    processed = merge_small_pixels_to_neighbors(
        color_blocks, source.width, source.height, pixel_size, 0.42,
    )
    assert labels[7, 10] == 5 and labels[8, 10] == 0 and labels[9, 10] == 5

    exported_occupancy = np.zeros(labels.shape, dtype=np.uint8)
    for block in processed:
        boxes = generate_optimized_boxes(
            block['pixels'], source.width, source.height, pixel_size, 0, 0.08,
        )
        block_value = 1 if (block['r'], block['g'], block['b']) == source_colors[0] else 2
        for (x0, x1), (y0, y1), (z0, z1) in boxes:
            assert (z0, z1) == (0, 0.08)
            x_start, x_end = round(x0 / pixel_size), round(x1 / pixel_size)
            y_start, y_end = round(y0 / pixel_size), round(y1 / pixel_size)
            assert x1 - x0 > 0 and y1 - y0 > 0
            exported_occupancy[y_start:y_end, x_start:x_end] = block_value

    assert np.all(exported_occupancy[7:10, 10] == 1)
    assert np.count_nonzero(exported_occupancy == 0) == 0
    assert source.width * pixel_size == 26 * pixel_size
    assert source.height * pixel_size == 22 * pixel_size
