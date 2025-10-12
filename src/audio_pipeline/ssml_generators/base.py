"""Base interfaces and helpers for locale-specific narrators."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Dict, Optional, Protocol

from src.audio_pipeline.localizers.money import MoneyAmount
from src.entities.candidate_record import CandidateRecord


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

    def constituency_segment(self, constituency_ssml: str) -> str:
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
    _NUMERIC_PATTERN = re.compile(r"[-+]?[0-9]+(?:[.,][0-9]+)?")
    _BASE_UNIT_MULTIPLIERS: Dict[str, Decimal] = {
        "crore": Decimal("10000000"),
        "lakh": Decimal("100000"),
        "thousand": Decimal("1000"),
        "million": Decimal("1000000"),
    }
    _HINGLISH_UNIT_ALIASES: Dict[str, set[str]] = {
        "crore": {"crore", "crores", "cr", "cr.", "karod", "karor", "cro"},
        "lakh": {"lakh", "lakhs", "lac", "lacs", "lack"},
        "thousand": {"thousand", "thousands", "k", "hazaar", "hazar"},
        "million": {"million", "millions", "mn"},
    }
    _DEVANAGARI_ALIASES: Dict[str, set[str]] = {
        "crore": {"\u0915\u0930\u094b\u0921", "\u0915\u0930\u094b\u095c"},
        "lakh": {"\u0932\u093e\u0916", "\u0932\u093e\u0916\u094b"},
        "thousand": {"\u0939\u091c\u093e\u0930", "\u0939\u091c\u093e\u0930\u094b"},
        "million": {"\u092e\u093f\u0932\u093f\u092f\u0928"},
    }
    _CURRENCY_TOKENS = ("rs.", "rs", "inr", "₹")

    def _with_mark(self, text: str, mark: str) -> str:
        if not text:
            return ""
        return f'{text}<mark name="{mark}"/>'

    def parse_money_amount(
        self, primary: str, fallback: str = ""
    ) -> Optional[MoneyAmount]:
        return self.__class__._parse_money_amount(primary, fallback)

    @classmethod
    def _parse_money_amount(
        cls, primary: str, fallback: str = ""
    ) -> Optional[MoneyAmount]:
        for candidate in (primary, fallback):
            amount = cls._parse_single_amount(candidate)
            if amount is not None:
                return amount
        return None

    @classmethod
    def _parse_single_amount(cls, value: str) -> Optional[MoneyAmount]:
        if not value:
            return None

        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "nan":
            return None

        normalised = cleaned.lower()
        for token in cls._CURRENCY_TOKENS:
            normalised = normalised.replace(token, "")

        numeric_match = cls._NUMERIC_PATTERN.search(normalised.replace(",", ""))
        if not numeric_match:
            return None

        number_token = numeric_match.group(0)
        try:
            magnitude = Decimal(number_token)
        except InvalidOperation:
            return None

        remaining = cls._NUMERIC_PATTERN.sub("", normalised)
        unit_key = cls._extract_unit_key(remaining)
        multiplier = cls._unit_multiplier(unit_key)
        rupees = (magnitude * multiplier).quantize(Decimal("1"))

        return MoneyAmount(
            rupees=rupees,
            magnitude=magnitude,
            unit_key=unit_key,
            raw_text=cleaned,
        )

    @classmethod
    def _extract_unit_key(cls, text: str) -> Optional[str]:
        for token in text.split():
            token_clean = token.strip().strip(".,")
            if not token_clean:
                continue
            canonical = cls._normalise_unit_key(token_clean)
            if canonical is not None:
                return canonical
        return None

    @classmethod
    def _unit_multiplier(cls, unit_key: Optional[str]) -> Decimal:
        if unit_key is None:
            return Decimal("1")
        return cls._BASE_UNIT_MULTIPLIERS.get(unit_key, Decimal("1"))

    @classmethod
    @lru_cache(maxsize=None)
    def _unit_alias_lookup(cls) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for canonical in cls._BASE_UNIT_MULTIPLIERS:
            lookup[canonical.lower()] = canonical

        for canonical, aliases in cls._HINGLISH_UNIT_ALIASES.items():
            for alias in aliases:
                lookup.setdefault(alias.lower(), canonical)

        for canonical, aliases in cls._DEVANAGARI_ALIASES.items():
            for alias in aliases:
                lookup.setdefault(alias.lower(), canonical)

        return lookup

    @classmethod
    def _normalise_unit_key(cls, raw: str) -> Optional[str]:
        return cls._unit_alias_lookup().get(raw.lower())


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
