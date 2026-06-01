"""Stdlib structured logging (no third-party dependency).

Emits one JSON object per line to stdout — ready for a PaaS log drain — with a per-request
``trace_id`` propagated via a ContextVar so every log line within one request correlates.
"""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone

from .config import LOG_LEVEL

# Set per request by the trace-ID middleware; "-" outside a request (startup, shutdown).
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

# Attributes present on a vanilla LogRecord — anything else passed via ``extra=`` is
# treated as a structured field and merged into the JSON line.
_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": trace_id_var.get(),
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger (idempotent)."""
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
