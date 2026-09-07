"""Logging utilities for CarryMem.

Supports optional structured (JSON) logging via the ``CARRYMEM_JSON_LOG``
environment variable. When set to ``"1"`` (or any truthy value parsed by
``str.lower() in ("1", "true", "yes")``), both file and console handlers
emit one JSON object per log record — convenient for shipping to Loki /
ELK / CloudWatch. Otherwise, the legacy human-readable formatter is used.

JSON schema (single line per record)::

    {"timestamp": "2026-07-20T10:11:12,123", "name": "carrymem",
     "level": "INFO", "message": "..."}
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any


def _is_json_log_enabled() -> bool:
    """Return True when ``CARRYMEM_JSON_LOG`` env var requests JSON output."""
    value = os.environ.get("CARRYMEM_JSON_LOG", "").strip().lower()
    return value in ("1", "true", "yes", "on")


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Uses ``json.dumps(..., ensure_ascii=False)`` so multi-byte messages
    (e.g., Chinese / Japanese) remain readable in non-JSON-aware tailers.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


class Logger:
    """Wrapper around :mod:`logging` with file and console handlers."""

    def __init__(self, name: str = "carrymem"):
        """Configure a named logger with file (INFO) and console (WARNING) handlers.

        When ``CARRYMEM_JSON_LOG`` is set to a truthy value, both handlers
        emit JSON-formatted lines (suitable for Loki / ELK ingestion).
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            use_json = _is_json_log_enabled()
            # Logs belong to the user's data home, never inside the package
            # tree (writing next to the module pollutes source checkouts and
            # installed site-packages alike). Override with CARRYMEM_LOG_DIR.
            logs_dir = os.environ.get("CARRYMEM_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".carrymem", "logs")
            try:
                os.makedirs(logs_dir, exist_ok=True)
                log_file = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.INFO)
                if use_json:
                    file_handler.setFormatter(JsonFormatter())
                else:
                    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
                self.logger.addHandler(file_handler)
            except OSError:
                pass

            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            if use_json:
                console_handler.setFormatter(JsonFormatter())
            else:
                console_handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(console_handler)
            self.logger.propagate = False

    def debug(self, message: str, *args, **kwargs):
        """Log a DEBUG-level message."""
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """Log an INFO-level message."""
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """Log a WARNING-level message."""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, exc_info: bool = False, **kwargs):
        """Log an ERROR-level message, optionally with exception info."""
        self.logger.error(message, *args, exc_info=exc_info, **kwargs)

    def critical(self, message: str, *args, exc_info: bool = False, **kwargs):
        """Log a CRITICAL-level message, optionally with exception info."""
        self.logger.critical(message, *args, exc_info=exc_info, **kwargs)


logger = Logger()
