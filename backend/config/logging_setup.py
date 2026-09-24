"""Log output: readable text locally, one JSON object per line in production.

Railway parses JSON log lines, so ``extra`` fields become filterable
attributes in its log explorer (for example ``@event:image_processed``).
"""
import json
import logging
from datetime import datetime, timezone

TEXT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Attributes every LogRecord has; anything else on a record came from ``extra``.
STANDARD_RECORD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
# Keys every JSON line starts with; ``extra`` fields must not overwrite them.
JSON_BASE_FIELDS = frozenset({"time", "level", "logger", "message", "exception"})


class JsonFormatter(logging.Formatter):
    """One JSON object per record, with ``extra`` fields as top-level keys."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            (key, value) for key, value in vars(record).items() if key not in STANDARD_RECORD_ATTRIBUTES
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(log_format: str, level: str) -> None:
    """Route the app's and uvicorn's logs through one handler in the chosen format."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if log_format == "json" else logging.Formatter(TEXT_FORMAT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers[:] = []
        uvicorn_logger.propagate = True
