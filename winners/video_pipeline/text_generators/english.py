"""English locale video text formatter."""

from __future__ import annotations

from typing import Dict, Optional

from winners.audio_pipeline.localizers.money import MoneyAmount
from winners.audio_pipeline.shared.money_parser import parse_money_amount as _parse_money_text
from winners.audio_pipeline.ssml_generators.base import _format_decimal_english
from winners.entities.candidate_record import CandidateRecord

from .base import VideoSegmentText, VideoTextFormatter

__all__ = ["EnglishVideoTextFormatter"]


class EnglishVideoTextFormatter(VideoTextFormatter):
    """Compose per-segment overlay text for English renders."""

    locale = "en"

    _CURRENCY_TOKENS = ("rs.", "rs", "inr", "₹")
    _UNIT_ALIASES = {
        "crore": ("crore", "crores", "cr", "cr.", "karod", "karor", "cro"),
        "lakh": ("lakh", "lakhs", "lac", "lacs", "lack"),
        "thousand": ("thousand", "thousands", "k"),
        "million": ("million", "millions", "mn"),
    }

    def segment_texts(self, record: CandidateRecord) -> Dict[str, VideoSegmentText]:
        segments: Dict[str, VideoSegmentText] = {}

        segments["name"] = self._name_segment(record)
        segments["party"] = self._party_segment(record)
        segments["constituency"] = self._constituency_segment(record)
        segments["age"] = self._age_segment(record)
        segments["education"] = self._education_segment(record)

        assets_amount = self._parse_money_amount(
            record.assets_description, record.total_assets
        )
        segments["assets"] = self._assets_segment(assets_amount)

        liabilities_amount = self._parse_money_amount(
            record.liabilities_description, record.total_liabilities
        )
        segments["liabilities"] = self._liabilities_segment(liabilities_amount)
        segments["criminal_cases"] = self._criminal_segment(record)


        return segments

    def _name_segment(self, record: CandidateRecord) -> VideoSegmentText:
        return VideoSegmentText(text=record.candidate_name.strip() or "Unknown Candidate")

    def _party_segment(self, record: CandidateRecord) -> VideoSegmentText:
        party = record.party.strip()
        if not party:
            primary = "Independent"
        elif party.lower() == "independent":
            primary = "Independent"
        else:
            primary = party
        return VideoSegmentText(text=primary)

    def _constituency_segment(self, record: CandidateRecord) -> VideoSegmentText:
        constituency = record.constituency.strip() or "Seat unspecified"
        return VideoSegmentText(text=constituency)

    def _age_segment(self, record: CandidateRecord) -> VideoSegmentText:
        age_value = record.age.strip()
        if age_value:
            primary = f"{age_value}"
        else:
            primary = "Unknown"
        return VideoSegmentText(text=primary)

    def _education_segment(self, record: CandidateRecord) -> VideoSegmentText:
        level = record.education.strip()
        details = record.education_details.strip()
        primary = level or "Education not reported"
        secondary = details or None
        return VideoSegmentText(text=primary)

    def _criminal_segment(self, record: CandidateRecord) -> VideoSegmentText:
        criminal_cases = record.criminal_cases.strip()
        if not criminal_cases:
            headline = "Criminal cases: Unknown"
        elif criminal_cases == "0":
            headline = " None"
        elif criminal_cases == "1":
            headline = "One"
        else:
            headline = f"{criminal_cases}"
        return VideoSegmentText(text=headline)

    def _assets_segment(self, amount: Optional[MoneyAmount]) -> VideoSegmentText:
        if amount is None:
            primary = "Not declared"
        elif amount.rupees == 0:
            primary = "0"
        else:
            primary = self._numeric_value(amount)
        return VideoSegmentText(text=primary)

    def _liabilities_segment(self, amount: Optional[MoneyAmount]) -> VideoSegmentText:
        if amount is None:
            primary = "Not declared"
        elif amount.rupees == 0:
            primary = "0"
        else:
            primary = "-"+self._numeric_value(amount)
        return VideoSegmentText(text=primary)

    def _parse_money_amount(
        self, primary: str, fallback: str = ""
    ) -> Optional[MoneyAmount]:
        return _parse_money_text(
            primary,
            fallback,
            aliases=self._UNIT_ALIASES,
            currency_tokens=self._CURRENCY_TOKENS,
        )

    def _numeric_value(self, amount: MoneyAmount) -> str:
        return _format_decimal_english(amount.rupees)
