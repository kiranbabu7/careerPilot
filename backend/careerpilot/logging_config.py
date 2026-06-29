"""Structured logging helpers and sensitive-data redaction."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone

_request_id = threading.local()

SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)(api[_-]?key|token|password|secret|authorization|bearer)\s*[:=]\s*['\"]?[\w\-./+=]{8,}",
        ),
        r"\1=***REDACTED***",
    ),
    (
        re.compile(r"(?i)(sk-[a-zA-Z0-9]{20,})"),
        r"***REDACTED***",
    ),
]


def get_request_id() -> str:
    return getattr(_request_id, "value", "-")


def set_request_id(value: str) -> None:
    _request_id.value = value


def clear_request_id() -> None:
    if hasattr(_request_id, "value"):
        del _request_id.value


def redact_sensitive_text(message: str) -> str:
    redacted = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            record.args = tuple(
                redact_sensitive_text(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
            "request_id": getattr(record, "request_id", get_request_id()),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def build_logging_config(*, debug: bool) -> dict:
    formatter_name = "json" if not debug else "verbose"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {"()": "careerpilot.logging_config.RequestIdFilter"},
            "redact_sensitive": {"()": "careerpilot.logging_config.SensitiveDataFilter"},
        },
        "formatters": {
            "verbose": {
                "format": "{levelname} {asctime} {name} request_id={request_id} {message}",
                "style": "{",
            },
            "json": {
                "()": "careerpilot.logging_config.JsonLogFormatter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "filters": ["request_id", "redact_sensitive"],
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "DEBUG" if debug else "INFO",
        },
        "loggers": {
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
            "apps": {
                "handlers": ["console"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            },
        },
    }
