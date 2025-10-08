"""Hindi narration formatter."""

from __future__ import annotations

from typing import Optional

from ..money import MoneyAmount
from .base import (
    LocaleFormatter,
    _DEVANAGARI_DIGITS,
    _FormatterBase,
    _format_decimal_indian,
)

try:  # pragma: no cover
    from ...election_entities import CandidateRecord
except ImportError:  # pragma: no cover
    from election_entities import CandidateRecord  # type: ignore

__all__ = ["HindiNarrationFormatter"]


class HindiNarrationFormatter(_FormatterBase, LocaleFormatter):
    locale = "hi"

    def name_segment(self, name_ssml: str, entity: CandidateRecord) -> str:
        return self._with_mark(f" Ummidvar ka naam: {name_ssml}", self.mark_name)

    def party_segment(self, party_text: str, party_ssml: str) -> str:
        if not party_text:
            return ""
        lower = party_text.lower()
        if lower == "independent":
            descriptor = "swayatantra prarthi hai"
        elif "party" in lower:
            descriptor = f"{party_ssml} dal se sambandhit hai"
        else:
            descriptor = f"{party_ssml} party se sambandhit hai"
        return self._with_mark(f", {descriptor}", self.mark_party)

    def constituency_segment(self, constituency_ssml: str) -> str:
        if not constituency_ssml:
            return ""
        phrase = f"{constituency_ssml} seat ke liye chunav lad rahe hain"
        return self._with_mark(f", {phrase}", self.mark_constituency)

    def age_segment(self, age_text: str) -> str:
        if not age_text:
            return ""
        translated = age_text.translate(_DEVANAGARI_DIGITS)
        return self._with_mark(f", umr {translated} varsh", self.mark_age)

    def education_segment(self, education_level: str, details: str) -> str:
        mapping = {
            "Doctorate": "doctorate shiksha prapt hai",
            "Post Graduate": "post graduate shiksha prapt hai",
            "Graduate": "graduate shiksha prapt hai",
            "Graduate Professional": "vyavsayik shiksha prapt hai",
            "12th Pass": "uchch madhyamik tak pathan kiya hai",
            "10th Pass": "madhyamik tak pathan kiya hai",
            "8th Pass": "madhyamik star tak pathan kiya hai",
            "5th Pass": "prathmik star ki shiksha hai",
            "Illiterate": "shikshit nahi hai",
            "Literate": "mool roop se shikshit hai",
            "Others": "anya shiksha prapt hai",
            "Not Given": "shiksha ki jankari uplabdh nahi",
        }
        base = mapping.get(
            education_level.strip(), f"{education_level or 'ashankit shiksha'}"
        )
        suffix = f" ({details})" if details else ""
        return self._with_mark(f", {base}{suffix}", self.mark_education)

    def criminal_segment(self, criminal_text: str) -> str:
        if criminal_text == "unknown":
            phrase = "aparadhik sthiti ajnayat hai"
        elif criminal_text == "0":
            phrase = "koi apradhik mamle nahi"
        elif criminal_text == "1":
            phrase = "ek apradhik mamla darj hai"
        else:
            phrase = (
                f"{criminal_text.translate(_DEVANAGARI_DIGITS)} apradhik mamle darj hain"
            )
        return self._with_mark(f", {phrase}", self.mark_criminal)

    def _numeric_phrase(self, amount: MoneyAmount) -> str:
        if amount.unit_key == "crore":
            unit = "crore"
            numeric = amount.magnitude
        elif amount.unit_key == "lakh":
            unit = "lakh"
            numeric = amount.magnitude
        elif amount.unit_key == "thousand":
            unit = "hazaar"
            numeric = amount.magnitude
        elif amount.unit_key == "million":
            unit = "million"
            numeric = amount.magnitude
        else:
            unit = "rupaye"
            numeric = amount.rupees

        formatted = _format_decimal_indian(numeric).translate(_DEVANAGARI_DIGITS)
        return f"{formatted} {unit}"

    def assets_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "sampatti ka maan uplabdh nahi"
        elif amount.rupees == 0:
            phrase = "koi sampatti ghoshit nahi"
        else:
            phrase = f"ghoshit sampatti {self._numeric_phrase(amount)}"
        return self._with_mark(phrase, self.mark_assets)

    def liabilities_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "rin ka maan uplabdh nahi"
        elif amount.rupees == 0:
            phrase = "koi rin darj nahi"
        else:
            phrase = f"ghoshit rin {self._numeric_phrase(amount)}"
        return self._with_mark(phrase, self.mark_liabilities)

    def combine_financial_segments(self, assets: str, liabilities: str) -> str:
        parts = [segment for segment in (assets, liabilities) if segment]
        if not parts:
            return ""
        return ", " + " aur ".join(parts)

