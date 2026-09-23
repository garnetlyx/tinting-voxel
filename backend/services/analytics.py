"""
Usage analytics service for tracking API endpoint usage.

Provides in-memory, thread-safe analytics with per-endpoint counts,
response times, and error rates. Persists nothing to disk — designed
for monitoring during an app lifecycle.

Memory-bounded with LRU eviction to prevent unbounded growth.
"""
import re
import threading
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class EndpointStats:
    """Stats for a single endpoint."""
    request_count: int = 0
    error_count: int = 0
    total_response_time_ms: float = 0.0
    last_request_at: Optional[str] = None


class AnalyticsCollector:
    """
    Thread-safe in-memory analytics collector with bounded memory.

    Uses LRU eviction to prevent unbounded growth. Max 10,000 unique
    endpoint keys are tracked. When limit is reached, least recently
    accessed endpoints are evicted.
    """

    # Maximum number of unique endpoint keys to track
    MAX_ENDPOINTS = 10_000

    # Known endpoints that should be tracked individually (not normalized)
    KNOWN_ENDPOINTS = {
        '/api/health',
        '/api/health/detailed',
        '/api/process-image',
        '/api/download-csv',
        '/api/filament-preview',
        '/api/filament-presets',
        '/api/analytics',
        '/api/palettes',
        '/api/palettes/',  # With trailing slash
        '/api/batch/process',
        '/api/batch/download-stl',
        '/api/process',  # Legacy endpoint
        # V2 endpoints
        '/api/v2/download-stl',
        '/api/v2/download-svg-stl',
        '/api/v2/download-3mf',
        '/api/v2/print-settings',
        '/api/v2/filament-presets',
    }

    # Path normalization patterns for parameterized endpoints
    PATH_PATTERNS = [
        (r'/api/palettes/[^/]+', '/api/palettes/{id}'),
        (r'/api/batch/[^/]+', '/api/batch/{action}'),
    ]

    def __init__(self):
        self._lock = threading.Lock()
        # Use OrderedDict for LRU tracking (move_to_end on access)
        self._endpoints: OrderedDict[str, EndpointStats] = OrderedDict()
        self._started_at = datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize parameterized paths to prevent key explosion."""
        # Known endpoints are returned as-is
        if path in AnalyticsCollector.KNOWN_ENDPOINTS:
            return path
        # Try specific patterns for parameterized endpoints
        for pattern, replacement in AnalyticsCollector.PATH_PATTERNS:
            if re.match(pattern, path):
                return replacement
        # Unknown /api/ paths get normalized to prevent key explosion
        if path.startswith('/api/'):
            return '/api/{unknown}'
        # Non-API paths return as-is
        return path

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
    ) -> None:
        """
        Record a single request with LRU eviction if at capacity.

        If endpoint doesn't exist and we're at MAX_ENDPOINTS,
        evict the least recently accessed endpoint.
        """
        normalized_path = self._normalize_path(path)
        key = f"{method} {normalized_path}"
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # Check if key exists
            if key in self._endpoints:
                # Move to end (mark as recently used)
                self._endpoints.move_to_end(key)
                stats = self._endpoints[key]
            else:
                # Check capacity before adding new endpoint
                if len(self._endpoints) >= self.MAX_ENDPOINTS:
                    # Evict least recently used (first item)
                    evicted_key = next(iter(self._endpoints))
                    del self._endpoints[evicted_key]

                # Create new stats entry
                stats = EndpointStats()
                self._endpoints[key] = stats

            # Update stats
            stats.request_count += 1
            stats.total_response_time_ms += response_time_ms
            stats.last_request_at = now
            if status_code >= 400:
                stats.error_count += 1

    def get_summary(self) -> dict:
        """Get a snapshot of all analytics data."""
        with self._lock:
            total_requests = sum(s.request_count for s in self._endpoints.values())
            total_errors = sum(s.error_count for s in self._endpoints.values())

            endpoints = {}
            for key, stats in sorted(self._endpoints.items()):
                avg_ms = (
                    stats.total_response_time_ms / stats.request_count
                    if stats.request_count > 0
                    else 0
                )
                endpoints[key] = {
                    'requestCount': stats.request_count,
                    'errorCount': stats.error_count,
                    'avgResponseTimeMs': round(avg_ms, 2),
                    'lastRequestAt': stats.last_request_at,
                }

            return {
                'startedAt': self._started_at,
                'totalRequests': total_requests,
                'totalErrors': total_errors,
                'endpoints': endpoints,
            }

    def reset(self) -> None:
        """Reset all analytics data (useful for testing)."""
        with self._lock:
            self._endpoints.clear()
            self._started_at = datetime.now(timezone.utc).isoformat()


# Global singleton
analytics = AnalyticsCollector()
