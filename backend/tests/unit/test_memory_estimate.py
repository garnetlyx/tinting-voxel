"""Unit tests for the heavy-job memory estimator (services/memory_estimate.py)."""
from services import memory_estimate


class TestFilamentPreview:
    def test_grows_with_combinations(self):
        small = memory_estimate.filament_preview_mb(5, 4, None)
        large = memory_estimate.filament_preview_mb(5, 9, None)
        assert large > small * 20  # 5^9 vs 5^4 entries, over the fixed floor

    def test_pagination_cuts_the_estimate(self):
        unpaginated = memory_estimate.filament_preview_mb(5, 10, None)
        paginated = memory_estimate.filament_preview_mb(5, 10, 10000)
        assert paginated < unpaginated / 100

    def test_suggest_paginates_before_reducing_layers(self):
        suggestion = memory_estimate.suggest_filament_preview(5, 10, None, budget_mb=500)
        assert suggestion is not None
        assert suggestion.pageSize == 10000
        assert suggestion.layerCount is None

    def test_suggest_reduces_layers_when_paginated_still_over(self):
        # A budget so small that even one page does not fit: layers come down.
        suggestion = memory_estimate.suggest_filament_preview(5, 10, None, budget_mb=0.001)
        assert suggestion is not None
        assert suggestion.layerCount == memory_estimate.MIN_SUGGESTED_LAYERS

    def test_no_suggestion_within_budget(self):
        assert memory_estimate.suggest_filament_preview(5, 4, None, budget_mb=3072) is None


class TestEnumeration:
    def test_distinct_counts_are_bounded(self):
        # 5^20 codes must not price 5^20 representatives.
        assert memory_estimate.enumeration_mb(5, 20) < 1024

    def test_short_opaque_sets_stay_honest(self):
        # Bambu CMYWK at 4 layers keeps all 625 codes distinct (review F5);
        # the bound must not assume opaque sets collapse to their labels.
        assert memory_estimate.enumeration_mb(4, 4) >= memory_estimate._mb(
            625 * (memory_estimate.ENUM_REP_BASE_BYTES + 4 * memory_estimate.ENUM_REP_PER_LAYER_BYTES),
        )

    def test_grows_with_labels_and_layers(self):
        assert memory_estimate.enumeration_mb(6, 8) > memory_estimate.enumeration_mb(5, 8)


class TestProcessImage:
    def test_pixel_grid_dominates_small_sets(self):
        estimate = memory_estimate.process_image_mb("pixel", 2_000_000, 5, 10, 10, True)
        assert 100 < estimate < 3072  # the crash-session job fits a single slot

    def test_suggest_reduces_layers_not_pixel_size(self):
        # Coarsening pixelSize cannot reduce the model grid (the grid keeps
        # the upload's resolution), so only layers may be suggested.
        suggestion = memory_estimate.suggest_process_image(
            "pixel", 2_000_000, 0.092, 5, 10, 10, True, budget_mb=1500,
        )
        assert suggestion is not None
        assert suggestion.layerCount is not None
        assert suggestion.layerCount >= memory_estimate.MIN_SUGGESTED_LAYERS
        assert suggestion.pixelSize is None
        # When even four layers do not fit (grid-dominated), there is no ask.
        assert memory_estimate.suggest_process_image(
            "pixel", 2_000_000, 0.092, 5, 10, 10, True, budget_mb=100,
        ) is None

    def test_no_suggestion_within_budget(self):
        assert memory_estimate.suggest_process_image(
            "pixel", 2_000_000, 0.092, 5, 10, 10, True, budget_mb=3072,
        ) is None


class TestDownload:
    def test_within_budget_has_no_suggestion(self):
        assert memory_estimate.suggest_download(2_000_000, 5, 10, True, budget_mb=3072) is None

    def test_suggests_fewer_layers_only(self):
        suggestion = memory_estimate.suggest_download(2_000_000, 5, 10, True, budget_mb=1300)
        assert suggestion is not None
        assert suggestion.layerCount is not None
        assert suggestion.pixelSize is None
        assert suggestion.layerCount >= memory_estimate.MIN_SUGGESTED_LAYERS

    def test_capped_by_stl_max_boxes(self):
        from config.settings import settings
        estimate = memory_estimate.download_mb(10_000_000, 10, 5, True)
        boxes = min(10_000_000 * 10, settings.stl_max_boxes)
        floor = memory_estimate.enumeration_mb(5, 13)
        assert estimate < memory_estimate._mb(boxes * memory_estimate.BOX_BYTES) + floor + 1


class TestBatch:
    def test_scales_with_images(self):
        assert memory_estimate.batch_mb(20, 100_000) > memory_estimate.batch_mb(1, 100_000) * 19


class TestGridCells:
    def test_small_images_keep_their_grid(self):
        assert memory_estimate.grid_cells(100, 50, 0.2, None) == 5000

    def test_large_images_are_bounded_by_max_cells(self):
        from config.settings import settings
        cells = memory_estimate.grid_cells(6000, 6000, 0.08, None)
        assert cells <= settings.max_model_cells + 6000  # rounding slack per side
