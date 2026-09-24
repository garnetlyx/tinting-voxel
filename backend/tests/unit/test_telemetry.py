"""Structured telemetry events and JSON log output."""
import json
import logging
from datetime import datetime, timezone

import services.telemetry as telemetry
from config.logging_setup import JsonFormatter
from services.analytics import analytics


def _record(message: str, **extra) -> logging.LogRecord:
    record = logging.makeLogRecord({"name": "telemetry", "levelno": logging.INFO, "levelname": "INFO", "msg": message})
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_puts_extra_fields_at_the_top_level():
    line = JsonFormatter().format(_record("image_processed", event="image_processed", duration_ms=1234))
    payload = json.loads(line)
    assert payload["level"] == "info"
    assert payload["logger"] == "telemetry"
    assert payload["message"] == "image_processed"
    assert payload["event"] == "image_processed"
    assert payload["duration_ms"] == 1234


def test_json_formatter_includes_exceptions():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = _record("failed")
        record.exc_info = sys.exc_info()
    assert "ValueError: boom" in json.loads(JsonFormatter().format(record))["exception"]


def test_emit_logs_fields_and_counts_the_event(caplog):
    analytics.reset()
    with caplog.at_level(logging.INFO, logger="telemetry"):
        telemetry.emit("model_exported", format="stl", bytes=10)
    record = next(r for r in caplog.records if r.name == "telemetry")
    assert (record.event, record.format, record.bytes) == ("model_exported", "stl", 10)
    assert analytics.get_summary()["events"] == {"model_exported": 1}


def test_visitor_id_is_daily_and_per_visitor(monkeypatch):
    days = iter([datetime(2026, 9, 23, tzinfo=timezone.utc)] * 3 + [datetime(2026, 9, 24, tzinfo=timezone.utc)])

    class FakeDatetime:
        @staticmethod
        def now(tz=None):
            return next(days)

    monkeypatch.setattr(telemetry, "datetime", FakeDatetime)
    monkeypatch.setattr(telemetry, "_salt", None)
    first = telemetry.visitor_id("203.0.113.7", "agent")
    assert telemetry.visitor_id("203.0.113.7", "agent") == first
    assert telemetry.visitor_id("198.51.100.1", "agent") != first
    assert telemetry.visitor_id("203.0.113.7", "agent") != first  # next day, new salt
    assert "203.0.113.7" not in first
