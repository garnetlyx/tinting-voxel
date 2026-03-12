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
    labels = np.array([[0, 1]], dtype=np.int32)
    colors = [
        (255, 0, 0),
        (0, 0, 255),
    ]

    cleaned = merge_small_label_regions(
        labels=labels,
        colors=colors,
        pixel_size=0.2,
        detail_size=0.4,
    )

    assert len(np.unique(cleaned)) == 1
