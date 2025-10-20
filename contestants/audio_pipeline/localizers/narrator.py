"""Narrator implementation combining formatters, money parsing, and phonetics."""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional, Protocol

from contestants.audio_pipeline.ssml_generators.base import LocaleFormatter
from contestants.audio_pipeline.phonetics.phonetics_generator import (
    generate_phoneme_string,
    generate_ssml_phonetics,
    generate_ssml_phonetics_native,
)
from contestants.entities.candidate_record import CandidateRecord


logger = logging.getLogger(__name__)

__all__ = ["CandidateNarrator", "LocalizedNarrator"]


class CandidateNarrator(Protocol):
    def ssml_segments(self, entity: CandidateRecord) -> Dict[str, str]:
        ...

    def ssml_text(
        self,
        entity: CandidateRecord,
        *,
        include_speak_wrapper: bool = True,
    ) -> str:
        ...


class LocalizedNarrator(CandidateNarrator):
    """Composes SSML output for a single locale."""

    def __init__(
        self,
        *,
        formatter: LocaleFormatter,
    ) -> None:
        self._formatter = formatter
        self._locale = getattr(formatter, "locale", "en")

    def _ssml_value(self, text: str) -> str:
        if not text:
            return ""
        if self._locale == "hi":
            try:
                return generate_ssml_phonetics_native(text)
            except Exception as exc:  # pragma: no cover - transliteration optional
                logger.warning(
                    "Hindi SSML generation failed for '%s': %s; falling back to plain text",
                    text,
                    exc,
                )
                return text

        try:
            return generate_ssml_phonetics(text)
        except Exception as exc:  # pragma: no cover - transliteration optional
            logger.warning(
                "SSML generation failed for '%s': %s; falling back to plain text",
                text,
                exc,
            )
            return text

    def _phoneme_value(self, text: str) -> str:
        if not text:
            return ""
        try:
            return generate_phoneme_string(text)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Phoneme generation failed for '%s': %s; returning plain text",
                text,
                exc,
            )
            return text

    def _criminal_value(self, criminal_cases: str) -> str:
        stripped = criminal_cases.strip()
        if not stripped:
            return "unknown"
        numeric_only = re.sub(r"[^0-9]", "", stripped)
        return numeric_only or "unknown"

    def ssml_segments(self, entity: CandidateRecord) -> Dict[str, str]:
        assets_amount = self._formatter.parse_money_amount(
            entity.assets_description, entity.total_assets
        )
        liabilities_amount = self._formatter.parse_money_amount(
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
            "age",
            "education",
        ]
        body = "".join(segments.get(key, "") for key in ordered_keys)

        financial = self._formatter.combine_financial_segments(
            segments.get("assets", ""), segments.get("liabilities", "")
        )
        body += financial 
        body += segments.get("criminal_cases", "")

        if include_speak_wrapper:
            return f"<speak>{body}</speak>"
        return body
