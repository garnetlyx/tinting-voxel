import logging
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from services.mesh_optimizer import generate_optimized_boxes
from services.raster_cleanup import merge_small_label_regions, regularize_printable_regions


def test_batch_merges_multiple_islands_into_stable_neighbors(caplog):
    """Independent islands touching a stable region should merge in one batch pass."""
    labels = np.array([
        [0, 0, 0],
        [0, 1, 0],
        [2, 0, 0],
    ], dtype=np.int32)
    colors = [
        (255, 0, 0),
        (0, 0, 255),
        (0, 255, 0),
    ]

    with caplog.at_level(logging.INFO):
        cleaned = merge_small_label_regions(
            labels=labels,
            colors=colors,
            pixel_size=0.2,
            detail_size=0.4,
        )

    assert np.all(cleaned == 0)
    assert "batch merged 2 undersized components" in caplog.text


def test_adjacent_small_components_converge_without_oscillation():
    """Small-small-large chains should converge to the stable region."""
    labels = np.array([[0, 1, 2, 2, 2, 2]], dtype=np.int32)
    colors = [
        (255, 0, 0),
        (250, 10, 10),
        (0, 0, 255),
    ]

    cleaned = merge_small_label_regions(
        labels=labels,
        colors=colors,
        pixel_size=0.2,
        detail_size=0.4,
    )

    assert np.all(cleaned == 2)


def test_fallback_merge_breaks_all_small_deadlock():
    """If no stable neighbor exists, cleanup still makes bounded progress."""
    labels = np.array([[0, 1, 2]], dtype=np.int32)
    colors = [
        (255, 0, 0),
        (250, 10, 10),
        (0, 0, 255),
    ]

    cleaned = merge_small_label_regions(
        labels=labels,
        colors=colors,
        pixel_size=0.2,
        detail_size=0.4,
    )

    assert len(np.unique(cleaned)) == 1


# ---------------------------------------------------------------------------
# Fix 2: fill_density stroke detection for connected border networks
# ---------------------------------------------------------------------------

def test_remove_thin_features_preserves_connected_border_network():
    """
    A connected network of thin lines (stained-glass border) must be preserved.

    The network spans a large bounding box but fills only a small fraction of
    it (low fill_density), so it should be classified as a stroke even though
    its bounding-box aspect ratio is close to 1.0.
    """
    from services.raster_cleanup import remove_thin_features

    H, W = 20, 20
    labels = np.zeros((H, W), dtype=np.int32)  # label 0 = fill color

    # Draw a thin connected border network (label 1) as a grid of 1px lines
    # spanning the full image — aspect ratio ≈ 1.0, fill_density ≈ 0.10
    for row in range(0, H, 4):
        labels[row, :] = 1
    for col in range(0, W, 4):
        labels[:, col] = 1

    border_pixel_count_before = int((labels == 1).sum())
    assert border_pixel_count_before > 0

    colors = [(200, 200, 200), (0, 0, 0)]  # fill=gray, border=black

    # pixel_size=0.1mm, detail_size=0.4mm → min_width=4px
    cleaned = remove_thin_features(
        labels=labels,
        colors=colors,
        pixel_size=0.1,
        detail_size=0.4,
    )

    # The border network must survive (may be dilated, but label 1 must remain)
    border_pixel_count_after = int((cleaned == 1).sum())
    assert border_pixel_count_after > 0, (
        "Connected border network was incorrectly deleted by remove_thin_features"
    )


def test_remove_thin_features_deletes_compact_noise():
    """
    A compact noise blob (high fill_density, low aspect_ratio) must be deleted.
    """
    from services.raster_cleanup import remove_thin_features

    H, W = 20, 20
    labels = np.zeros((H, W), dtype=np.int32)

    # 3×3 compact blob of label 1 in the center — aspect_ratio=1.0, fill_density=1.0
    labels[8:11, 8:11] = 1

    colors = [(200, 200, 200), (0, 0, 0)]

    cleaned = remove_thin_features(
        labels=labels,
        colors=colors,
        pixel_size=0.1,
        detail_size=0.4,
    )

    # The compact blob should be reassigned to label 0
    assert int((cleaned == 1).sum()) == 0, (
        "Compact noise blob was not removed by remove_thin_features"
    )


def test_remove_thin_features_reassigns_to_spatial_neighbor_not_top_left_origin():
    """
    Ensure noise pixels are reassigned to their true spatial neighbors rather
    than erroneously indexing top-left pixels from flat array mismatch.
    """
    from services.raster_cleanup import remove_thin_features

    H, W = 50, 50
    # Top-left has label 0
    labels = np.zeros((H, W), dtype=np.int32)
    # Bottom-right has label 1
    labels[25:, 25:] = 1
    # Inside bottom-right, put a tiny 2x2 noise blob of label 2 at (40:42, 40:42)
    labels[40:42, 40:42] = 2

    colors = [(0, 0, 255), (255, 0, 0), (0, 255, 0)]  # 0=blue, 1=red, 2=green

    cleaned = remove_thin_features(
        labels=labels,
        colors=colors,
        pixel_size=0.1,
        detail_size=0.4,
    )

    # The noise blob was deep inside label 1 (red). It must become label 1, NOT label 0 (blue)
    assert np.all(cleaned[40:42, 40:42] == 1), (
        f"Noise blob was incorrectly reassigned to {cleaned[40:42, 40:42]} instead of neighbor 1"
    )



def test_multicolor_region_cleanup_matches_pre_optimization_output():
    """The old 4-neighbor merge is the pixel-exact oracle for this texture."""
    from hashlib import sha256

    y, x = np.indices((40, 48))
    labels = ((x // 3 + 2 * (y // 4)) % 5).astype(np.int32)
    rng = np.random.default_rng(7)
    ys = rng.integers(0, 40, 130)
    xs = rng.integers(0, 48, 130)
    labels[ys, xs] = rng.integers(0, 5, 130)
    colors = [
        (255, 0, 0), (0, 0, 255), (0, 255, 0),
        (255, 255, 0), (0, 0, 0),
    ]
    expected = {
        0.13: (245, "e5c7f60ca95f8e00eb82ccb3bd98262c6aba7ee66cffc0c2ef84007925b300f9"),
        0.16: (84, "b1835a29312f2f1db87e131b624046b77613e5162c8b547fe7a0c6dc275625da"),
        0.22: (79, "8093738acbf691335df933242732815f5e7954ce2530a6c884e691ef538413eb"),
    }

    for pixel_size, (changed, digest) in expected.items():
        cleaned = merge_small_label_regions(labels, colors, pixel_size, 0.42)
        assert cleaned.dtype == labels.dtype
        assert int((cleaned != labels).sum()) == changed
        assert sha256(cleaned.astype("<i4").tobytes()).hexdigest() == digest


def test_single_color_component_has_no_background_id():
    """A filled label can have no background pixels in the OpenCV label map."""
    labels = np.full((6, 8), 2, dtype=np.int32)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    cleaned = merge_small_label_regions(labels, colors, 0.13, 0.42)
    assert np.array_equal(cleaned, labels)
    assert cleaned.dtype == labels.dtype


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
