import logging

import numpy as np

from services.raster_cleanup import merge_small_label_regions


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
