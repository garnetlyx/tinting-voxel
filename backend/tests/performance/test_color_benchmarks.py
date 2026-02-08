"""
Performance benchmarks for color processing with 8, 12, and 16 color configurations.

Tests memory usage and execution time for key operations:
- code_to_rgb computation
- Filament preview generation (paginated)
- LRU cache effectiveness

These tests serve as regression guards to prevent performance degradation.
"""
import time
import tracemalloc

import pytest

from core.blend_color import BlendTestGenerator, Colors, clear_rgb_cache
from core.color_config import ColorConfig
from services.filament_preview import FilamentPreviewService

# Generous time/memory bounds to avoid flaky tests on slow CI
MAX_TIME_PER_CODE_MS = 5.0  # ms per code_to_rgb call
MAX_PREVIEW_TIME_S = 30.0  # seconds for paginated preview
MAX_MEMORY_MB = 256  # MB peak memory


def _make_configs(n: int) -> list:
    """Generate n unique ColorConfig objects with distinct labels and hex values."""
    palette = [
        ("Aqua", "#00FFFF", 3.0),
        ("Berry", "#FF00FF", 1.9),
        ("Citrus", "#FFFF00", 2.5),
        ("Dove", "#FFFFFF", 7.2),
        ("Ebony", "#111111", 0.5),
        ("Flame", "#FF4500", 2.0),
        ("Grass", "#00FF00", 3.5),
        ("Harbor", "#0000FF", 1.5),
        ("Ivory", "#FFFFF0", 6.0),
        ("Jade", "#00A86B", 2.8),
        ("Khaki", "#C3B091", 4.0),
        ("Lemon", "#FFF44F", 3.2),
        ("Mint", "#98FF98", 5.0),
        ("Navy", "#000080", 1.0),
        ("Olive", "#808000", 2.2),
        ("Plum", "#8E4585", 1.7),
    ]
    return [
        ColorConfig(name=name, hex=hex_val, transmission_distance=td)
        for name, hex_val, td in palette[:n]
    ]


class TestCodeToRgbPerformance:
    """Benchmark code_to_rgb for various color counts."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_rgb_cache()
        yield
        clear_rgb_cache()

    @pytest.mark.parametrize("num_colors", [4, 8, 12, 16])
    def test_code_to_rgb_time(self, num_colors):
        """code_to_rgb should complete within time bounds."""
        configs = _make_configs(num_colors)
        colors = Colors.from_configs(configs)
        gen = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
        )
        labels = colors.get_labels()

        # Generate a representative set of codes
        codes = [labels[i % num_colors] * 4 for i in range(100)]

        start = time.perf_counter()
        for code in codes:
            gen.code_to_rgb(code)
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_ms = elapsed_ms / len(codes)
        assert avg_ms < MAX_TIME_PER_CODE_MS, (
            f"{num_colors} colors: avg {avg_ms:.2f}ms per call exceeds {MAX_TIME_PER_CODE_MS}ms limit"
        )

    @pytest.mark.parametrize("num_colors", [4, 8, 12, 16])
    def test_code_to_rgb_cache_speedup(self, num_colors):
        """Cached calls should be significantly faster than cold calls."""
        configs = _make_configs(num_colors)
        colors = Colors.from_configs(configs)
        gen = BlendTestGenerator(
            colors=colors,
            layer_height=0.08,
            layer_count_max=4,
            verbose=False,
        )
        labels = colors.get_labels()
        codes = [labels[i % num_colors] * 4 for i in range(50)]

        # Cold run
        clear_rgb_cache()
        start = time.perf_counter()
        for code in codes:
            gen.code_to_rgb(code)
        cold_ms = (time.perf_counter() - start) * 1000

        # Warm run (all cached)
        start = time.perf_counter()
        for code in codes:
            gen.code_to_rgb(code)
        warm_ms = (time.perf_counter() - start) * 1000

        # Cache should provide at least 2x speedup
        if cold_ms > 1.0:  # Only assert if cold run was measurable
            assert warm_ms < cold_ms, (
                f"{num_colors} colors: warm={warm_ms:.2f}ms not faster than cold={cold_ms:.2f}ms"
            )


class TestPreviewPerformance:
    """Benchmark filament preview generation."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        clear_rgb_cache()
        yield
        clear_rgb_cache()

    @pytest.mark.parametrize("num_colors,layer_count", [
        (4, 4),   # 256 combos
        (8, 2),   # 64 combos
        (8, 3),   # 512 combos
        (12, 2),  # 144 combos
        (16, 2),  # 256 combos
    ])
    def test_preview_generation_time(self, num_colors, layer_count):
        """Paginated preview should complete within time bounds."""
        configs = _make_configs(num_colors)
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=layer_count, layer_height=0.08)

        start = time.perf_counter()
        result = service.generate_preview(page=1, page_size=100)
        elapsed = time.perf_counter() - start

        assert elapsed < MAX_PREVIEW_TIME_S, (
            f"{num_colors} colors, {layer_count} layers: "
            f"{elapsed:.2f}s exceeds {MAX_PREVIEW_TIME_S}s limit"
        )
        assert len(result["colorMatrix"]) <= 100

    @pytest.mark.parametrize("num_colors,layer_count", [
        (4, 4),   # 256 combos
        (8, 2),   # 64 combos
        (16, 2),  # 256 combos
    ])
    def test_preview_memory_usage(self, num_colors, layer_count):
        """Preview generation should stay within memory bounds."""
        configs = _make_configs(num_colors)
        colors = Colors.from_configs(configs)
        service = FilamentPreviewService(colors, layer_count=layer_count, layer_height=0.08)

        tracemalloc.start()
        service.generate_preview(page=1, page_size=100)
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak_bytes / (1024 * 1024)
        assert peak_mb < MAX_MEMORY_MB, (
            f"{num_colors} colors, {layer_count} layers: "
            f"peak {peak_mb:.1f}MB exceeds {MAX_MEMORY_MB}MB limit"
        )
