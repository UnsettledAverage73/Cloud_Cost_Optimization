"""
CloudPulse Production SRE Structured Logging Engine
Google Cloud & Kubernetes compatible JSON log formatter with distributed correlation ID propagation.
"""

import json
import logging
import contextvars
from datetime import datetime, timezone
from typing import Optional, Any, Dict

# Context variable for current request's trace/correlation ID
correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("correlation_id_ctx", default=None)


class SREJsonFormatter(logging.Formatter):
    """
    Google Cloud Logging (Stackdriver) & Kubernetes SRE compatible JSON formatter.
    Translates standard Python logging records into structured JSON.
    """

    LEVEL_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "severity": self.LEVEL_MAP.get(record.levelname, record.levelname),
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "logger": record.name,
            "message": record.getMessage(),
            "sourceLocation": {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }
        }

        # Inject active request correlation ID if available
        req_id = correlation_id_ctx.get() or getattr(record, "correlation_id", None)
        if req_id:
            log_payload["correlation_id"] = req_id
            log_payload["logging.googleapis.com/trace"] = f"projects/cloudpulse/traces/{req_id}"

        # Include exception traceback if present
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        # Include any extra metadata passed via extra={"extra_fields": ...}
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_payload.update(record.extra_fields)

        return json.dumps(log_payload)


def configure_structured_logging(level: str = "INFO", use_json: bool = True):
    """Configures root logger with SRE JSON formatter."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicate logs
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    if use_json:
        handler.setFormatter(SREJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        )

    root.addHandler(handler)
    return root
