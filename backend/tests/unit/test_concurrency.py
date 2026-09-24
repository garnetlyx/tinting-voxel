"""
Concurrency tests for thread safety of global state and shared resources.

Tests thread safety of global color mapping state and analytics memory bounding.
"""
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.blend_color import Colors
from core.color_config import ColorConfig
from services import stl_generator
from services.analytics import AnalyticsCollector


class TestGlobalStateThreadSafety:
    """Test thread safety of global color mapping state."""

    def test_concurrent_initialize_color_mapping(self):
        """Test that concurrent initializations don't cause race conditions."""
        # Create different color configurations
        configs = [
            [
                ColorConfig(name="C", hex="#00FFFF", transmission_distance=0.8),
                ColorConfig(name="M", hex="#FF00FF", transmission_distance=0.8),
                ColorConfig(name="Y", hex="#FFFF00", transmission_distance=0.8),
                ColorConfig(name="W", hex="#FFFFFF", transmission_distance=0.8),
            ],
            [
                ColorConfig(name="R", hex="#FF0000", transmission_distance=1.0),
                ColorConfig(name="G", hex="#00FF00", transmission_distance=1.0),
                ColorConfig(name="B", hex="#0000FF", transmission_distance=1.0),
                ColorConfig(name="W", hex="#FFFFFF", transmission_distance=1.0),
            ],
        ]

        errors = []

        def init_colors(config_list):
            try:
                colors = Colors.from_configs(config_list)
                stl_generator.initialize_color_mapping(
                    layer_count=4,
                    layer_height=0.08,
                    colors=colors
                )
            except Exception as e:
                errors.append(e)

        # Run 10 concurrent initializations
        threads = []
        for i in range(10):
            config = configs[i % 2]
            thread = threading.Thread(target=init_colors, args=(config,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without errors
        assert len(errors) == 0, f"Concurrent initialization errors: {errors}"

    def test_concurrent_stl_generation_with_global_fallback(self):
        """Test concurrent STL generation using global color fallback."""
        # Initialize global state once
        stl_generator.initialize_color_mapping()

        # Sample color blocks (must match Pydantic models)
        color_blocks = [
            {
                'hex': '#FF0000',
                'r': 255, 'g': 0, 'b': 0,
                'count': 3,
                'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 2, 'y': 0}]
            },
            {
                'hex': '#00FF00',
                'r': 0, 'g': 255, 'b': 0,
                'count': 3,
                'pixels': [{'x': 0, 'y': 1}, {'x': 1, 'y': 1}, {'x': 2, 'y': 1}]
            }
        ]

        results = []
        errors = []

        def generate_stl():
            try:
                # Use None colors to trigger global state read
                zip_bytes = stl_generator.generate_stl_zip(
                    color_blocks=color_blocks,
                    layer_height=0.08,
                    pixel_size=0.08,
                    layer_count=4,
                    image_dimensions={'width': 10, 'height': 10},
                    use_greedy_meshing=True,
                    colors=None  # Trigger global state read
                )
                results.append(len(zip_bytes))
            except Exception as e:
                errors.append(e)

        # Run 20 concurrent generations
        threads = []
        for _ in range(20):
            thread = threading.Thread(target=generate_stl)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without errors
        assert len(errors) == 0, f"Concurrent generation errors: {errors}"
        # All results should be positive (valid ZIP)
        assert all(r > 0 for r in results)
        # All results should be similar (same input)
        assert max(results) - min(results) < 1000, "Results vary too much"


class TestAnalyticsConcurrency:
    """Analytics recording is thread safe."""

    def test_concurrent_analytics_recording(self):
        """Test thread safety of analytics recording."""
        collector = AnalyticsCollector()

        def record_requests(endpoint_id, count):
            for i in range(count):
                collector.record_request(
                    method='POST',
                    route=f'/api/endpoint/{endpoint_id}',
                    status_code=200 if i % 10 != 0 else 500,
                    response_time_ms=15.0 + (i % 50)
                )

        # Run 10 threads recording 100 requests each
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(record_requests, i, 100)
                for i in range(10)
            ]
            for future in as_completed(futures):
                future.result()

        summary = collector.get_summary()
        # Should have recorded 1000 requests total
        assert summary['totalRequests'] == 1000
        assert len(summary['endpoints']) == 10


class TestIntegrationConcurrency:
    """Integration tests for concurrent operations."""

    def test_mixed_concurrent_operations(self):
        """Test mixed concurrent operations don't interfere."""
        # Initialize global state
        stl_generator.initialize_color_mapping()

        # Create analytics collector
        analytics = AnalyticsCollector()

        errors = []
        results = {'stl': [], 'analytics': []}

        def stl_task():
            try:
                color_blocks = [
                    {'hex': '#FF0000', 'r': 255, 'g': 0, 'b': 0, 'count': 2,
                     'pixels': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}]}
                ]
                zip_bytes = stl_generator.generate_stl_zip(
                    color_blocks=color_blocks,
                    layer_height=0.08,
                    pixel_size=0.08,
                    layer_count=4,
                    image_dimensions={'width': 10, 'height': 10},
                    colors=None
                )
                results['stl'].append(len(zip_bytes))
            except Exception as e:
                errors.append(('stl', e))

        def analytics_task(endpoint_id):
            try:
                for _ in range(10):
                    analytics.record_request(
                        method='GET',
                        route=f'/api/test/{endpoint_id}',
                        status_code=200,
                        response_time_ms=20.0
                    )
                results['analytics'].append(endpoint_id)
            except Exception as e:
                errors.append(('analytics', e))

        # Run STL generation and analytics updates concurrently.
        threads = []
        for i in range(10):
            threads.append(threading.Thread(target=stl_task))
            threads.append(threading.Thread(target=analytics_task, args=(i,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without errors
        assert len(errors) == 0, f"Concurrent operations errors: {errors}"
        # Both task types should have completed.
        assert len(results['stl']) == 10
        assert len(results['analytics']) == 10
