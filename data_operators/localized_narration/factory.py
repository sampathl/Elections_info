"""Factory helpers for constructing localized narrators."""

from __future__ import annotations

from typing import Dict, Optional, Type

from .formatters import EnglishNarrationFormatter, HindiNarrationFormatter, LocaleFormatter
from .money import MoneyParser
from .narrator import LocalizedNarrator

__all__ = ["CandidateNarratorFactory"]


class CandidateNarratorFactory:
    """Factory delivering narrator instances for a given locale."""

    _FORMATTERS: Dict[str, Type[LocaleFormatter]] = {
        "en": EnglishNarrationFormatter,
        "hi": HindiNarrationFormatter,
    }

    def __init__(
        self,
        *,
        money_parser: Optional[MoneyParser] = None,
    ) -> None:
        self._money_parser = money_parser or MoneyParser()

    def create(self, locale: str) -> LocalizedNarrator:
        formatter_cls = self._FORMATTERS.get(locale)
        if formatter_cls is None:
            raise ValueError(f"Unsupported locale '{locale}'")

        formatter = formatter_cls()
        return LocalizedNarrator(
            formatter=formatter,
            money_parser=self._money_parser,
        )
