"""Hindi narration formatter."""

from __future__ import annotations

from typing import Optional

from src.audio_pipeline.localizers.money import MoneyAmount
from src.audio_pipeline.ssml_generators.base import (
    LocaleFormatter,
    _DEVANAGARI_DIGITS,
    _FormatterBase,
    _format_decimal_indian,
)

from src.audio_pipeline.localizers.candidate_record import CandidateRecord

__all__ = ["HindiNarrationFormatter"]


class HindiNarrationFormatter(_FormatterBase, LocaleFormatter):
    locale = "hi"

    def name_segment(self, name_ssml: str, entity: CandidateRecord) -> str:
        return self._with_mark(f" उम्मीदवार का नाम: {name_ssml}", self.mark_name)

    def party_segment(self, party_text: str, party_ssml: str) -> str:
        if not party_text:
            return ""
        lower = party_text.lower()
        if lower == "independent":
            descriptor = "<break time='200ms'/> स्वतंत्र प्रत्याशी हैं"
        elif "party" in lower:
            descriptor = f"<break time='200ms'/> {party_ssml} दल से संबद्ध हैं"
        else:
            descriptor = f"<break time='200ms'/> {party_ssml} पार्टी से संबद्ध हैं"
        return self._with_mark(f", {descriptor}", self.mark_party)

    def constituency_segment(self, constituency_ssml: str) -> str:
        if not constituency_ssml:
            return ""
        phrase = f"{constituency_ssml} सीट के लिए चुनाव लड़ रहे हैं"
        return self._with_mark(f", {phrase}", self.mark_constituency)

    def age_segment(self, age_text: str) -> str:
        if not age_text:
            return ""
        translated = age_text.translate(_DEVANAGARI_DIGITS)
        return self._with_mark(f", उम्र {translated} वर्ष", self.mark_age)

    def education_segment(self, education_level: str, details: str) -> str:
        mapping = {
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
            "Not Given": "शिक्षा की जानकारी उपलब्ध नहीं है",
        }
        base = mapping.get(
            education_level.strip(), f"{education_level or 'अस्पष्ट शिक्षा'}"
        )
        suffix = f" ({details})" if details else ""
        return self._with_mark(f", {base}{suffix}", self.mark_education)

    def criminal_segment(self, criminal_text: str) -> str:
        if criminal_text == "unknown":
            phrase = "आपराधिक स्थिति अज्ञात है"
        elif criminal_text == "0":
            phrase = "कोई आपराधिक मामला दर्ज नहीं है"
        elif criminal_text == "1":
            phrase = "एक आपराधिक मामला दर्ज है"
        else:
            phrase = (
                f"<break time='200ms'/> {criminal_text.translate(_DEVANAGARI_DIGITS)} आपराधिक मामले दर्ज हैं"
            )
        return self._with_mark(f", {phrase}", self.mark_criminal)

    def _numeric_phrase(self, amount: MoneyAmount) -> str:
        if amount.unit_key == "crore":
            unit = "करोड़"
            numeric = amount.magnitude
        elif amount.unit_key == "lakh":
            unit = "लाख"
            numeric = amount.magnitude
        elif amount.unit_key == "thousand":
            unit = "हज़ार"
            numeric = amount.magnitude
        elif amount.unit_key == "million":
            unit = "मिलियन"
            numeric = amount.magnitude
        else:
            unit = "रुपये"
            numeric = amount.rupees

        formatted = _format_decimal_indian(numeric).translate(_DEVANAGARI_DIGITS)
        return f"{formatted} {unit}"

    def assets_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "संपत्ति का मूल्य उपलब्ध नहीं है"
        elif amount.rupees == 0:
            phrase = "कोई संपत्ति घोषित नहीं की गई है"
        else:
            phrase = f"घोषित संपत्ति {self._numeric_phrase(amount)} की है"
        return self._with_mark(phrase, self.mark_assets)

    def liabilities_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "ऋण का मूल्य उपलब्ध नहीं है"
        elif amount.rupees == 0:
            phrase = "कोई ऋण दर्ज नहीं है"
        else:
            phrase = f"घोषित ऋण {self._numeric_phrase(amount)} का है"
        return self._with_mark(phrase, self.mark_liabilities)

    def combine_financial_segments(self, assets: str, liabilities: str) -> str:
        parts = [segment for segment in (assets, liabilities) if segment]
        if not parts:
            return ""
        return ", " + " और ".join(parts)
