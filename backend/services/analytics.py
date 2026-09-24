"""
In-memory usage summary since startup: per-route request counts, errors and
response times, plus telemetry event counts (services/telemetry.py).

Routes are recorded by their template (for example ``/api/palettes/{palette_id}``),
so the key set is bounded by the app's routes.
"""
import threading
from collections import Counter
from dataclasses import dataclass
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
    """Thread-safe in-memory counters."""

    def __init__(self):
        self._lock = threading.Lock()
        self._endpoints: dict[str, EndpointStats] = {}
        self._events: Counter[str] = Counter()
        self._started_at = datetime.now(timezone.utc).isoformat()

    def record_request(
        self,
        method: str,
        route: str,
        status_code: int,
        response_time_ms: float,
    ) -> None:
        """Record a single request against its route template."""
        key = f"{method} {route}"
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            stats = self._endpoints.setdefault(key, EndpointStats())
            stats.request_count += 1
            stats.total_response_time_ms += response_time_ms
            stats.last_request_at = now
            if status_code >= 400:
                stats.error_count += 1

    def record_event(self, event: str) -> None:
        with self._lock:
            self._events[event] += 1

    def get_summary(self) -> dict:
        """Get a snapshot of all analytics data."""
        with self._lock:
            total_requests = sum(s.request_count for s in self._endpoints.values())
            total_errors = sum(s.error_count for s in self._endpoints.values())
            endpoints = {
                key: {
                    'requestCount': stats.request_count,
                    'errorCount': stats.error_count,
                    'avgResponseTimeMs': round(stats.total_response_time_ms / stats.request_count, 2),
                    'lastRequestAt': stats.last_request_at,
                }
                for key, stats in sorted(self._endpoints.items())
            }
            return {
                'startedAt': self._started_at,
                'totalRequests': total_requests,
                'totalErrors': total_errors,
                'endpoints': endpoints,
                'events': dict(sorted(self._events.items())),
            }

    def reset(self) -> None:
        """Reset all analytics data (useful for testing)."""
        with self._lock:
            self._endpoints.clear()
            self._events.clear()
            self._started_at = datetime.now(timezone.utc).isoformat()


# Global singleton
analytics = AnalyticsCollector()
