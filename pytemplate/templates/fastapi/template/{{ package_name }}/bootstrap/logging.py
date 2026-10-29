"""Structured logging: JSON or text, the request ID on every record, and secrets redacted."""

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

REDACTED = "[REDACTED]"
_SECRET = re.compile(
    r"(?i)\b(authorization|x-api-key|api[_-]?key|token|password|secret)"
    r"([\"']?\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s,;\"']+"
)
_EXTRA_FIELDS = ("method", "path", "status", "duration_ms", "event", "subject", "outcome")
_HANDLER_MARKER = "_pytemplate_handler"


def redact(text: str) -> str:
    """Mask credential-looking values such as `Authorization: Bearer ...` or `api_key=...`."""
    return _SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}", text)


class ContextFilter(logging.Filter):
    """Attach the current request ID and redact secrets from the rendered message."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Annotate one record; never drops it."""
        record.__dict__["request_id"] = request_id.get()
        record.msg = redact(record.getMessage())
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    """Render one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a record with its request ID and selected extra fields."""
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": record.__dict__.get("request_id"),
        }
        for key in _EXTRA_FIELDS:
            if key in record.__dict__:
                payload[key] = record.__dict__[key]
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str)


def configure_logging(level: str, log_format: str) -> None:
    """Install one handler on the root logger, replacing any installed by an earlier call."""
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter()
        if log_format == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
    )
    setattr(handler, _HANDLER_MARKER, True)
    root = logging.getLogger()
    for existing in [h for h in root.handlers if getattr(h, _HANDLER_MARKER, False)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
