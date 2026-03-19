"""ECS-compliant structured logging for the investment package.

Usage::

    from investment.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Processing request", extra={"symbol": "AAPL"})
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Standard LogRecord attributes that should not be treated as ECS extra fields.
_STANDARD_ATTRS: frozenset[str] = frozenset(
    [
        "args",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    ]
)


class _EcsFormatter(logging.Formatter):
    """Formats log records as single-line JSON following the Elastic Common Schema."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        entry: dict[str, Any] = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "log.level": record.levelname.lower(),
            "log.logger": record.name,
            "message": record.message,
            "service.name": os.getenv("ELASTIC_APM_SERVICE_NAME", "investment"),
        }

        apm_env = os.getenv("ELASTIC_APM_ENVIRONMENT")
        if apm_env:
            entry["service.environment"] = apm_env

        if record.exc_info:
            entry["error.message"] = self.formatException(record.exc_info)

        # Merge any caller-supplied extra fields.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value

        return json.dumps(entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """Return an ECS-formatted logger for the given module name.

    The log level is controlled by the ``LOG_LEVEL`` environment variable
    (default: ``INFO``).  Each logger receives a single ``StreamHandler``
    writing to *stderr*; duplicate handlers are never added.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_EcsFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    raw_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(getattr(logging, raw_level, logging.INFO))

    return logger
