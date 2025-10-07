"""Shared logging utilities for the YouTube connector."""

from __future__ import annotations

import logging
from typing import Dict

from . import config

_LOGGER_CACHE: Dict[str, logging.Logger] = {}


def get_logger(name: str) -> logging.Logger:
    """Return a cached logger that writes to the shared connector log file."""
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_path = config.LOG_FILE_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    )
    handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(handler)

    _LOGGER_CACHE[name] = logger
    return logger
