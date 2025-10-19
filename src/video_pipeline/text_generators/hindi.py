"""Hindi locale video text formatter."""

from __future__ import annotations

from typing import Dict, Optional

from src.audio_pipeline.localizers.money import MoneyAmount
from src.audio_pipeline.shared.money_parser import parse_money_amount as _parse_money_text
from src.audio_pipeline.ssml_generators.base import (
    _DEVANAGARI_DIGITS,
    _format_decimal_indian,
)
from src.audio_pipeline.phonetics.phonetics_generator import (
    generate_native_transliteration,
)
from src.entities.candidate_record import CandidateRecord

from .base import VideoSegmentText, VideoTextFormatter

__all__ = ["HindiVideoTextFormatter"]


class HindiVideoTextFormatter(VideoTextFormatter):
    """Compose per-segment overlay text for Hindi renders."""

    locale = "hi"

    _CURRENCY_TOKENS = ("rs.", "rs", "inr", "₹")
    _UNIT_ALIASES = {
        "crore": ("crore", "crores", "cr", "cr.", "karod", "karor"),
        "lakh": ("lakh", "lakhs", "lac", "lacs"),
        "thousand": ("thousand", "thousands", "k"),
        "million": ("million", "millions", "mn"),
    }

    _EDUCATION_DESCRIPTIONS = {
        "Doctorate": "डॉक्टरेट की उपाधि प्राप्त है",
        "Post Graduate": "स्नातकोत्तर शिक्षा प्राप्त है",
        "Graduate": "स्नातक शिक्षा प्राप्त है",
        "Graduate Professional": "व्यावसायिक स्नातक शिक्षा प्राप्त है",
        "12th Pass": "उच्च माध्यमिक तक पढ़ाई की है",
        "10th Pass": "माध्यमिक तक पढ़ाई की है",
        "8th Pass": "मध्य स्तर तक पढ़ाई की है",
        "5th Pass": "प्राथमिक स्तर की शिक्षा प्राप्त है",
        "Illiterate": "शिक्षित नहीं हैं",
        "Literate": "मूल रूप से शिक्षित हैं",
        "Others": "अन्य शिक्षा प्राप्त है",
        "Not Given": " ",
    }

    def segment_texts(self, record: CandidateRecord) -> Dict[str, VideoSegmentText]:
        segments: Dict[str, VideoSegmentText] = {}

        segments["name"] = self._name_segment(record)
        segments["party"] = self._party_segment(record)
        segments["constituency"] = self._constituency_segment(record)
        segments["age"] = self._age_segment(record)
        segments["education"] = self._education_segment(record)
        segments["criminal_cases"] = self._criminal_segment(record)

        assets_amount = self._parse_money_amount(
            record.assets_description, record.total_assets
        )
        segments["assets"] = self._assets_segment(assets_amount)

        liabilities_amount = self._parse_money_amount(
            record.liabilities_description, record.total_liabilities
        )
        segments["liabilities"] = self._liabilities_segment(liabilities_amount)

        return segments

    def _name_segment(self, record: CandidateRecord) -> VideoSegmentText:
        primary_source = record.candidate_name.strip()
        primary = self._transliterate(primary_source) if primary_source else "अज्ञात उम्मीदवार"
        return VideoSegmentText(text=primary)

    def _party_segment(self, record: CandidateRecord) -> VideoSegmentText:
        party = record.party.strip()
        if not party:
            primary = "स्वतंत्र उम्मीदवार"
        elif party.lower() == "independent":
            primary = "स्वतंत्र उम्मीदवार"
        else:
            primary = self._transliterate(party)
        return VideoSegmentText(text=primary)

    def _constituency_segment(self, record: CandidateRecord) -> VideoSegmentText:
        constituency_source = record.constituency.strip()
        if constituency_source:
            primary = self._transliterate(constituency_source)
        else:
            primary = "अज्ञात निर्वाचन क्षेत्र"
        return VideoSegmentText(text=primary)

    def _age_segment(self, record: CandidateRecord) -> VideoSegmentText:
        age_value = record.age.strip()
        if age_value:
            translated = age_value.translate(_DEVANAGARI_DIGITS)
            primary = f"{translated}"
        else:
            primary = " उपलब्ध नहीं"
        return VideoSegmentText(text=primary)

    def _education_segment(self, record: CandidateRecord) -> VideoSegmentText:
        level_key = record.education.strip()
        if level_key:
            level = self._EDUCATION_DESCRIPTIONS.get(level_key, level_key)
        else:
            level = "शिक्षा उपलब्ध नहीं"
        return VideoSegmentText(text=level)

    def _criminal_segment(self, record: CandidateRecord) -> VideoSegmentText:
        criminal_cases = record.criminal_cases.strip()
        if not criminal_cases:
            primary = " अज्ञात"
        elif criminal_cases == "0":
            primary = " नहीं"
        elif criminal_cases == "1":
            primary = " १"
        else:
            primary = f" {criminal_cases.translate(_DEVANAGARI_DIGITS)}"
        return VideoSegmentText(text=primary)

    def _assets_segment(self, amount: Optional[MoneyAmount]) -> VideoSegmentText:
        if amount is None:
            primary = "उपलब्ध नहीं"
        elif amount.rupees == 0:
            primary = "०"
        else:
            primary = self._numeric_value(amount)
        return VideoSegmentText(text=primary)

    def _liabilities_segment(self, amount: Optional[MoneyAmount]) -> VideoSegmentText:
        if amount is None:
            primary = "उपलब्ध नहीं"
        elif amount.rupees == 0:
            primary = "०"
        else:
            primary = self._numeric_value(amount)
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
        numeric = _format_decimal_indian(amount.rupees)
        return numeric.translate(_DEVANAGARI_DIGITS)

    def _transliterate(self, text: str) -> str:
        if not text:
            return ""
        try:
            return generate_native_transliteration(text)
        except Exception:
            return text
