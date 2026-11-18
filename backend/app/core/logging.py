"""Structured logging configuration."""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_NOISY_LOGGERS = ("uvicorn.access", "httpx", "urllib3")


def configure_logging(level: str = "INFO") -> None:
    """Install a single stdout handler on the root logger (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers = [handler]
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    _CONFIGURED = True
