"""Centralised logging helpers for the winners pipelines."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Optional

__all__ = [
    "DEFAULT_CONTEXT",
    "PipelineLoggerAdapter",
    "setup_logging",
    "get_pipeline_logger",
]


DEFAULT_CONTEXT: Mapping[str, str] = {
    "candidate": "-",
    "locale": "-",
    "segment": "-",
    "component": "-",
}


class _ContextDefaultsFilter(logging.Filter):
    """Ensure every log record has the expected contextual keys."""

    def __init__(self, required: Mapping[str, str]) -> None:
        super().__init__()
        self._required = required

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - thin wrapper
        for key, value in self._required.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class PipelineLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that carries structured context across pipeline stages."""

    def __init__(self, logger: logging.Logger, extra: Optional[MutableMapping[str, object]] = None) -> None:
        super().__init__(logger, extra or {})

    # The LoggerAdapter process method is intentionally simple so we can merge context.
    def process(self, msg, kwargs):  # pragma: no cover - delegated to stdlib
        extra = kwargs.get("extra")
        if extra:
            merged = {**DEFAULT_CONTEXT, **self.extra, **extra}
        else:
            merged = {**DEFAULT_CONTEXT, **self.extra}
        kwargs["extra"] = merged
        return msg, kwargs

    def bind(self, **kwargs: object) -> "PipelineLoggerAdapter":
        """Return a new adapter with additional contextual information."""
        merged: Dict[str, object] = {**self.extra, **kwargs}
        return PipelineLoggerAdapter(self.logger, merged)


def setup_logging(
    log_dir: Path | str,
    *,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    file_name: str = "winner_pipeline.log",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> Path:
    """Configure root logging with both console and rotating file handlers."""

    resolved_dir = Path(log_dir).expanduser().resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    log_path = resolved_dir / file_name

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s "
            "[candidate=%(candidate)s locale=%(locale)s segment=%(segment)s component=%(component)s] "
            "%(message)s"
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addFilter(_ContextDefaultsFilter(DEFAULT_CONTEXT))

    logging.captureWarnings(True)
    return log_path


def get_pipeline_logger(name: str, **context: object) -> PipelineLoggerAdapter:
    """Return a logger adapter preloaded with pipeline context defaults."""
    logger = logging.getLogger(name)
    adapter = PipelineLoggerAdapter(logger, dict(context) if context else {})
    return adapter
