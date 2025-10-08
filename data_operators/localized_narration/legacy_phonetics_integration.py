"""Legacy phonetics_engine integration preserved for future reference.

This module keeps the pre-refactor narrator and factory implementations that
depended on ``phonetics_engine``. They are not imported anywhere by default,
but remain available if the project reinstates direct usage of those helpers.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional

from .formatters import LocaleFormatter
from .money import MoneyParser
from .narrator import CandidateNarrator

try:  # pragma: no cover - keep optional dependency guards as before
    from ..phonetics_engine import (
        PhoneticsProvider,
        TranscriberRegistry,
        TransliterationUnavailable,
    )
except ImportError:  # pragma: no cover
    PhoneticsProvider = None  # type: ignore
    TranscriberRegistry = None  # type: ignore
    TransliterationUnavailable = RuntimeError  # type: ignore

try:  # pragma: no cover
    from ..election_entities import CandidateRecord
except ImportError:  # pragma: no cover
    from election_entities import CandidateRecord  # type: ignore

logger = logging.getLogger(__name__)

__all__ = ["LegacyLocalizedNarrator", "LegacyCandidateNarratorFactory"]


class LegacyLocalizedNarrator(CandidateNarrator):
    """Previous LocalizedNarrator that relied on PhoneticsProvider injections."""

    def __init__(
        self,
        *,
        formatter: LocaleFormatter,
        money_parser: MoneyParser,
        phonetics: Optional[PhoneticsProvider] = None,
    ) -> None:
        self._formatter = formatter
        self._money_parser = money_parser
        self._phonetics = phonetics

    def _ssml_value(self, text: str) -> str:
        if not text:
            return ""
        if self._phonetics is None:
            return text
        try:
            return self._phonetics.to_ssml(text)
        except Exception as exc:  # pragma: no cover - optional dependency at runtime
            logger.warning("Phonetics generation failed for '%s': %s", text, exc)
            return text

    def _criminal_value(self, criminal_cases: str) -> str:
        stripped = criminal_cases.strip()
        if not stripped:
            return "unknown"
        numeric_only = re.sub(r"[^0-9]", "", stripped)
        return numeric_only or "unknown"

    def ssml_segments(self, entity: CandidateRecord) -> Dict[str, str]:
        assets_amount = self._money_parser.parse(
            entity.assets_description, entity.total_assets
        )
        liabilities_amount = self._money_parser.parse(
            entity.liabilities_description, entity.total_liabilities
        )

        name_segment = self._formatter.name_segment(
            self._ssml_value(entity.candidate_name), entity
        )

        party_segment = self._formatter.party_segment(
            entity.party, self._ssml_value(entity.party)
        )

        constituency_segment = self._formatter.constituency_segment(
            self._ssml_value(entity.constituency)
        )

        age_segment = self._formatter.age_segment(entity.age.strip())
        education_segment = self._formatter.education_segment(
            entity.education.strip(), entity.education_details.strip()
        )

        criminal_segment = self._formatter.criminal_segment(
            self._criminal_value(entity.criminal_cases)
        )

        assets_segment = self._formatter.assets_segment(assets_amount)
        liabilities_segment = self._formatter.liabilities_segment(liabilities_amount)

        segments = {
            "name": name_segment,
            "party": party_segment,
            "constituency": constituency_segment,
            "age": age_segment,
            "education": education_segment,
            "criminal_cases": criminal_segment,
            "assets": assets_segment,
            "liabilities": liabilities_segment,
        }
        return segments

    def ssml_text(
        self,
        entity: CandidateRecord,
        *,
        include_speak_wrapper: bool = True,
    ) -> str:
        segments = self.ssml_segments(entity)
        ordered_keys = [
            "name",
            "party",
            "constituency",
            "age",
            "education",
            "criminal_cases",
        ]
        body = "".join(segments.get(key, "") for key in ordered_keys)

        financial = self._formatter.combine_financial_segments(
            segments.get("assets", ""), segments.get("liabilities", "")
        )
        body += financial

        if include_speak_wrapper:
            return f"<speak>{body}</speak>"
        return body


class LegacyCandidateNarratorFactory:
    """Preserved factory that constructed narrators with phonetics support."""

    _FORMATTERS: Dict[str, type[LocaleFormatter]] = {
        "en": None,  # lazily initialised to avoid circular imports
        "hi": None,
    }

    def __init__(
        self,
        *,
        money_parser: Optional[MoneyParser] = None,
        transcriber_registry: Optional[TranscriberRegistry] = None,
    ) -> None:
        from .formatters import EnglishNarrationFormatter, HindiNarrationFormatter

        self._money_parser = money_parser or MoneyParser()
        if transcriber_registry is not None:
            self._registry = transcriber_registry
        elif TranscriberRegistry is not None:
            self._registry = TranscriberRegistry()
        else:
            self._registry = None

        self._FORMATTERS["en"] = EnglishNarrationFormatter
        self._FORMATTERS["hi"] = HindiNarrationFormatter

    def _resolve_phonetics(self, locale: str) -> Optional[PhoneticsProvider]:
        if PhoneticsProvider is None or self._registry is None:
            return None

        locale_to_config = {
            "en": ("hi", "Deva"),
            "hi": ("hi", "Deva"),
        }

        config = locale_to_config.get(locale)
        if not config:
            return None

        lang, script = config
        try:
            return self._registry.get(lang, script)
        except TransliterationUnavailable as exc:  # pragma: no cover
            logger.info("Phonetics unavailable for %s-%s: %s", lang, script, exc)
            return None

    def create(self, locale: str) -> LegacyLocalizedNarrator:
        formatter_cls = self._FORMATTERS.get(locale)
        if formatter_cls is None:
            raise ValueError(f"Unsupported locale '{locale}'")

        formatter = formatter_cls()  # type: ignore[call-arg]
        phonetics = self._resolve_phonetics(locale)
        return LegacyLocalizedNarrator(
            formatter=formatter,
            money_parser=self._money_parser,
            phonetics=phonetics,
        )

