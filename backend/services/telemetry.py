"""Structured usage and operations events.

Each event is one record on the "telemetry" logger whose fields become
top-level JSON keys in production logs (config/logging_setup.py), so Railway's
log explorer can filter them, e.g. ``@event:image_processed AND
@duration_ms:>5000``. Event counts since startup also appear in
``/api/analytics``.

Visitors are counted with a salted hash that rotates every UTC day and is never
stored; no IP address or user agent is logged.
"""
import hashlib
import logging
import secrets
import threading
from datetime import date, datetime, timezone

from config.logging_setup import JSON_BASE_FIELDS, STANDARD_RECORD_ATTRIBUTES
from services.analytics import analytics

logger = logging.getLogger("telemetry")

# Field names an event cannot use: LogRecord attributes, JSON line keys and the event name.
RESERVED_FIELDS = STANDARD_RECORD_ATTRIBUTES | JSON_BASE_FIELDS | {"event"}
# Fields the server adds to every browser event.
CLIENT_CONTEXT_FIELDS = frozenset({"visitor", "page", "at_ms"})

_salt_lock = threading.Lock()
_salt: tuple[date, bytes] | None = None


def emit(event: str, **fields) -> None:
    """Record one event with its fields."""
    analytics.record_event(event)
    logger.info(event, extra={"event": event, **fields})


def visitor_id(client_address: str, user_agent: str) -> str:
    """Anonymous visitor key: stable within one UTC day, unlinkable across days."""
    global _salt
    today = datetime.now(timezone.utc).date()
    with _salt_lock:
        if _salt is None or _salt[0] != today:
            _salt = (today, secrets.token_bytes(16))
        salt = _salt[1]
    digest = hashlib.sha256(salt + client_address.encode() + b"\0" + user_agent.encode())
    return digest.hexdigest()[:16]
