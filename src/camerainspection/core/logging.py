"""Structured JSON logging with audit context tracking for OEM traceability."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class AuditJsonFormatter(logging.Formatter):
    """Formats log records as structured JSON entries."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Extract audit context if present
        for key in ("seat_id", "station_id", "variant_id", "outcome", "cycle_ms", "trace_id"):
            val = getattr(record, key, None)
            if val is not None:
                log_payload[key] = val

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure system-wide structured logging to console."""
    root_logger = logging.getLogger("camerainspection")
    root_logger.setLevel(level)

    # Avoid duplicate handlers if re-configured
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(AuditJsonFormatter())
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Retrieve a namespaced logger."""
    return logging.getLogger(f"camerainspection.{name}")
