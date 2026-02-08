"""
Unit tests for the analytics service.
"""
import threading

from services.analytics import AnalyticsCollector


class TestAnalyticsCollector:
    """Tests for AnalyticsCollector."""

    def test_empty_summary(self):
        """New collector has zero counts."""
        collector = AnalyticsCollector()
        summary = collector.get_summary()
        assert summary['totalRequests'] == 0
        assert summary['totalErrors'] == 0
        assert summary['endpoints'] == {}
        assert 'startedAt' in summary

    def test_record_single_request(self):
        """Record a single successful request."""
        collector = AnalyticsCollector()
        collector.record_request('GET', '/api/health', 200, 5.0)
        summary = collector.get_summary()
        assert summary['totalRequests'] == 1
        assert summary['totalErrors'] == 0
        assert 'GET /api/health' in summary['endpoints']
        ep = summary['endpoints']['GET /api/health']
        assert ep['requestCount'] == 1
        assert ep['errorCount'] == 0
        assert ep['avgResponseTimeMs'] == 5.0

    def test_record_error_request(self):
        """Error responses increment error count."""
        collector = AnalyticsCollector()
        collector.record_request('POST', '/api/process', 500, 10.0)
        summary = collector.get_summary()
        assert summary['totalErrors'] == 1
        ep = summary['endpoints']['POST /api/process']
        assert ep['errorCount'] == 1

    def test_4xx_counts_as_error(self):
        """4xx status codes count as errors."""
        collector = AnalyticsCollector()
        collector.record_request('POST', '/api/process', 400, 2.0)
        summary = collector.get_summary()
        assert summary['totalErrors'] == 1

    def test_multiple_requests_same_endpoint(self):
        """Multiple requests to same endpoint aggregate correctly."""
        collector = AnalyticsCollector()
        collector.record_request('GET', '/api/health', 200, 5.0)
        collector.record_request('GET', '/api/health', 200, 15.0)
        summary = collector.get_summary()
        ep = summary['endpoints']['GET /api/health']
        assert ep['requestCount'] == 2
        assert ep['avgResponseTimeMs'] == 10.0

    def test_multiple_different_endpoints(self):
        """Requests to different endpoints tracked separately."""
        collector = AnalyticsCollector()
        collector.record_request('GET', '/api/health', 200, 1.0)
        collector.record_request('POST', '/api/process', 200, 100.0)
        summary = collector.get_summary()
        assert len(summary['endpoints']) == 2
        assert summary['totalRequests'] == 2

    def test_reset_clears_data(self):
        """Reset clears all tracked data."""
        collector = AnalyticsCollector()
        collector.record_request('GET', '/api/health', 200, 5.0)
        collector.reset()
        summary = collector.get_summary()
        assert summary['totalRequests'] == 0
        assert summary['endpoints'] == {}

    def test_last_request_at_updated(self):
        """Last request timestamp is updated on each request."""
        collector = AnalyticsCollector()
        collector.record_request('GET', '/api/health', 200, 1.0)
        summary = collector.get_summary()
        ep = summary['endpoints']['GET /api/health']
        assert ep['lastRequestAt'] is not None

    def test_thread_safety(self):
        """Concurrent writes don't corrupt data."""
        collector = AnalyticsCollector()
        n_threads = 10
        n_requests_per_thread = 100

        def record_many():
            for _ in range(n_requests_per_thread):
                collector.record_request('GET', '/api/health', 200, 1.0)

        threads = [threading.Thread(target=record_many) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        summary = collector.get_summary()
        assert summary['totalRequests'] == n_threads * n_requests_per_thread
