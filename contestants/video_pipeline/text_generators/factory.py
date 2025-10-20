"""Factory helpers for constructing locale-specific video text generators."""

from __future__ import annotations

from typing import Dict, Type

from .base import VideoTextFormatter
from .english import EnglishVideoTextFormatter
from .hindi import HindiVideoTextFormatter

__all__ = ["VideoTextFactory"]


class VideoTextFactory:
    """Factory delivering video text formatter instances for a given locale."""

    _FORMATTERS: Dict[str, Type[VideoTextFormatter]] = {
        "en": EnglishVideoTextFormatter,
        "hi": HindiVideoTextFormatter,
    }

    def create(self, locale: str) -> VideoTextFormatter:
        formatter_cls = self._FORMATTERS.get(locale)
        if formatter_cls is None:
            raise ValueError(f"Unsupported locale '{locale}'")
        return formatter_cls()
