"""Factory helpers for constructing localized narrators."""

from __future__ import annotations

from typing import Dict, Type

from winners.audio_pipeline.ssml_generators.english import EnglishNarrationFormatter
from winners.audio_pipeline.ssml_generators.hindi import HindiNarrationFormatter
from winners.audio_pipeline.ssml_generators.base import LocaleFormatter
from winners.audio_pipeline.localizers.narrator import LocalizedNarrator

__all__ = ["CandidateNarratorFactory"]


class CandidateNarratorFactory:
    """Factory delivering narrator instances for a given locale."""

    _FORMATTERS: Dict[str, Type[LocaleFormatter]] = {
        "en": EnglishNarrationFormatter,
        "hi": HindiNarrationFormatter,
    }

    def __init__(self) -> None:
        pass

    def create(self, locale: str) -> LocalizedNarrator:
        formatter_cls = self._FORMATTERS.get(locale)
        if formatter_cls is None:
            raise ValueError(f"Unsupported locale '{locale}'")

        formatter = formatter_cls()
        return LocalizedNarrator(formatter=formatter)
