"""Base interfaces and helpers for locale-specific narrators."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Protocol

from winners.audio_pipeline.localizers.money import MoneyAmount
from winners.entities.candidate_record import CandidateRecord


__all__ = [
    "LocaleFormatter",
    "_FormatterBase",
    "_format_decimal_english",
    "_format_decimal_indian",
    "_DEVANAGARI_DIGITS",
]


class LocaleFormatter(Protocol):
    locale: str

    def parse_money_amount(
        self, primary: str, fallback: str = ""
    ) -> Optional[MoneyAmount]:
        ...

    def name_segment(self, name_ssml: str, entity: CandidateRecord) -> str:
        ...

    def party_segment(self, party_text: str, party_ssml: str) -> str:
        ...

    def constituency_segment(self, constituency_ssml: str, *, year: str = "") -> str:
        ...

    def age_segment(self, age_text: str) -> str:
        ...

    def education_segment(self, education_level: str, details: str) -> str:
        ...

    def criminal_segment(self, criminal_text: str) -> str:
        ...

    def assets_segment(self, amount: Optional[MoneyAmount]) -> str:
        ...

    def liabilities_segment(self, amount: Optional[MoneyAmount]) -> str:
        ...

    def combine_financial_segments(self, assets: str, liabilities: str) -> str:
        ...


class _FormatterBase:
    mark_name = "name"
    mark_party = "party"
    mark_constituency = "constituency"
    mark_age = "age"
    mark_education = "education"
    mark_criminal = "criminal_cases"
    mark_assets = "assets"
    mark_liabilities = "liabilities"

    def _with_mark(self, text: str, mark: str) -> str:
        if not text:
            return ""
        return f'{text}<mark name="{mark}"/>'


def _format_decimal_english(value: Decimal) -> str:
    quantised = value.quantize(Decimal("1")) if value == value.to_integral() else value
    number = f"{quantised:,}"
    return number


def _format_decimal_indian(value: Decimal) -> str:
    string_value = f"{value:f}" if value != value.to_integral() else str(int(value))
    if "." in string_value:
        integer_part, fractional_part = string_value.split(".", 1)
    else:
        integer_part, fractional_part = string_value, ""

    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while remaining:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        grouped = ",".join(groups + [last_three])

    if fractional_part:
        fractional_part = fractional_part.rstrip("0")
    return grouped if not fractional_part else f"{grouped}.{fractional_part}"


_DEVANAGARI_DIGITS = str.maketrans(
    "0123456789", "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f"
)
