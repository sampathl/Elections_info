"""English narration formatter."""

from __future__ import annotations

from typing import Optional

from winners.audio_pipeline.localizers.money import MoneyAmount
from winners.audio_pipeline.shared.money_parser import parse_money_amount as _parse_money_text
from winners.audio_pipeline.ssml_generators.base import (
    LocaleFormatter,
    _FormatterBase,
    _format_decimal_english,
)
from winners.entities.candidate_record import CandidateRecord

__all__ = ["EnglishNarrationFormatter"]


class EnglishNarrationFormatter(_FormatterBase, LocaleFormatter):
    locale = "en"
    _CURRENCY_TOKENS = ("rs.", "rs", "inr", "₹")
    _UNIT_ALIASES = {
        "crore": ("crore", "crores", "cr", "cr.", "karod", "karor", "cro"),
        "lakh": ("lakh", "lakhs", "lac", "lacs", "lack"),
        "thousand": ("thousand", "thousands", "k"),
        "million": ("million", "millions", "mn"),
    }

    def parse_money_amount(
        self, primary: str, fallback: str = ""
    ) -> Optional[MoneyAmount]:
        return _parse_money_text(
            primary,
            fallback,
            aliases=self._UNIT_ALIASES,
            currency_tokens=self._CURRENCY_TOKENS,
        )

    def name_segment(self, name_ssml: str, entity: CandidateRecord) -> str:
        return self._with_mark(f" Candidate name: {name_ssml},", self.mark_name)

    def party_segment(self, party_text: str, party_ssml: str) -> str:
        if not party_text:
            return ""
        lower = party_text.lower()
        if lower == "independent":
            descriptor = "is an independent candidate."
        elif "party" in lower:
            descriptor = f"is a member of the {party_ssml}."
        else:
            descriptor = f"is a member of the {party_ssml} party."
        return self._with_mark(f", {descriptor}", self.mark_party)

    def constituency_segment(self, constituency_ssml: str, year: str) -> str:
        if not constituency_ssml:
            return ""
        return self._with_mark(
            ", contesting for the, {constituency} seat".format(
                constituency=constituency_ssml,
                year = year
            ),
            self.mark_constituency,
        )

    def age_segment(self, age_text: str) -> str:
        if not age_text:
            return ""
        return self._with_mark(f"aged {age_text}.", self.mark_age)

    def education_segment(self, education_level: str, details: str) -> str:
        descriptions = {
            "Doctorate": "holds a doctorate degree",
            "Post Graduate": "holds a post graduate degree",
            "Graduate": "holds a graduate degree",
            "Graduate Professional": "is a graduate professional",
            "12th Pass": "has completed higher secondary education",
            "10th Pass": "has completed secondary education",
            "8th Pass": "has completed middle school",
            "5th Pass": "has primary education",
            "Illiterate": "is illiterate",
            "Literate": "is literate with unspecified formal education",
            "Others": "has other educational qualifications",
            "Not Given": "has unspecified educational background",
        }
        base = descriptions.get(
            education_level.strip(),
            "had {education} education".format(education=education_level or "unspecified"),
        )
        suffix = f" ({details})" if details else ""
        return self._with_mark(f" {base}, {suffix}.", self.mark_education)

    def criminal_segment(self, criminal_text: str) -> str:
        if criminal_text == "unknown":
            phrase = "legal standing is not known"
        elif criminal_text == "0":
            phrase = "has no criminal cases on record"
        elif criminal_text == "1":
            phrase = "has one criminal case on record"
        else:
            phrase = f"has {criminal_text} criminal cases on record"
        return self._with_mark(f" {phrase}.", self.mark_criminal)

    def _numeric_phrase(self, amount: MoneyAmount) -> str:
        if amount.unit_key == "crore":
            unit_text = "crore"
            numeric = amount.magnitude
        elif amount.unit_key == "lakh":
            unit_text = "lakh"
            numeric = amount.magnitude
        elif amount.unit_key == "thousand":
            unit_text = "thousand"
            numeric = amount.magnitude
        elif amount.unit_key == "million":
            unit_text = "million"
            numeric = amount.magnitude
        else:
            unit_text = "rupees"
            numeric = amount.rupees

        formatted = _format_decimal_english(numeric)
        return f"{formatted} {unit_text}"

    def assets_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "assets of unkown value."
        elif amount.rupees == 0:
            phrase = "no assets declared."
        else:
            phrase = f"assets valued at {self._numeric_phrase(amount)}."
        return self._with_mark(phrase, self.mark_assets)

    def liabilities_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = ",liabilities of unkown value."
        elif amount.rupees == 0:
            phrase = ", no liabilities declared."
        else:
            phrase = f", liabilities amounting to {self._numeric_phrase(amount)}."
        return self._with_mark(phrase, self.mark_liabilities)

    def combine_financial_segments(self, assets: str, liabilities: str) -> str:
        fragments = [fragment for fragment in (assets, liabilities) if fragment]
        if not fragments:
            return ""
        joined = " and ".join(fragments)
        return f", {joined}"
