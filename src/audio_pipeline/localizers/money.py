"""Money parsing utilities shared by localized narrators."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

__all__ = ["MoneyAmount", "MoneyParser"]


@dataclass(frozen=True)
class MoneyAmount:
    """Structured financial value expressed in rupees."""

    rupees: Decimal
    magnitude: Decimal
    unit_key: Optional[str]
    raw_text: str


class MoneyParser:
    """Parse textual assets/liabilities into normalised ``MoneyAmount`` values."""

    _NUMERIC_PATTERN = re.compile(r"[-+]?[0-9]+(?:[.,][0-9]+)?")
    _UNIT_MULTIPLIERS: Dict[str, Decimal] = {
        "crore": Decimal("10000000"),
        "karod": Decimal("10000000"),
        "lakh": Decimal("100000"),
        "lac": Decimal("100000"),
        "lacs": Decimal("100000"),
        "hazar": Decimal("1000"),
        "thousand": Decimal("1000"),
        "thousands": Decimal("1000"),
        "million": Decimal("1000000"),
        "mn": Decimal("1000000"),
    }

    _HINGLISH_UNIT_ALIASES = {
        "crore": {"crore", "crores", "cr", "cr.", "karod", "karor", "cro"},
        "lakh": {"lakh", "lakhs", "lac", "lacs", "lack"},
        "thousand": {"thousand", "thousands", "k", "hazaar", "hazar"},
        "million": {"million", "millions", "mn"},
    }

    # Inject proper Devanagari spellings while keeping the mapping ASCII-only.
    _DEVANAGARI_ALIASES = {
        "crore": {"\u0915\u0930\u094b\u0921", "\u0915\u0930\u094b\u095c"},
        "lakh": {"\u0932\u093e\u0916", "\u0932\u093e\u0916\u094b"},
        "thousand": {"\u0939\u091c\u093e\u0930", "\u0939\u091c\u093e\u0930\u094b"},
        "million": {"\u092e\u093f\u0932\u093f\u092f\u0928"},
    }

    def __init__(self) -> None:
        # Populate unit lookup with Hinglish/Devanagari aliases.
        for unit_key, aliases in self._HINGLISH_UNIT_ALIASES.items():
            multiplier = self._UNIT_MULTIPLIERS.get(unit_key, Decimal("1"))
            for alias in aliases:
                self._UNIT_MULTIPLIERS.setdefault(alias, multiplier)
        for unit_key, aliases in self._DEVANAGARI_ALIASES.items():
            multiplier = self._UNIT_MULTIPLIERS.get(unit_key, Decimal("1"))
            for alias in aliases:
                self._UNIT_MULTIPLIERS.setdefault(alias, multiplier)

    def parse(self, primary: str, fallback: str = "") -> Optional[MoneyAmount]:
        """Return the first successfully parsed amount from provided strings."""

        for candidate in (primary, fallback):
            result = self._parse_single(candidate)
            if result is not None:
                return result
        return None

    def _parse_single(self, value: str) -> Optional[MoneyAmount]:
        if not value:
            return None

        cleaned = value.strip()
        if not cleaned or cleaned.lower() == "nan":
            return None

        normalised = cleaned.lower()
        normalised = (
            normalised.replace("rs.", "")
            .replace("rs", "")
            .replace("inr", "")
            .replace("₹", "")
        )

        numeric_match = self._NUMERIC_PATTERN.search(normalised.replace(",", ""))
        if not numeric_match:
            return None

        number_token = numeric_match.group(0)
        try:
            magnitude = Decimal(number_token)
        except InvalidOperation:
            return None

        remaining = self._NUMERIC_PATTERN.sub("", normalised)

        unit_key = self._extract_unit_key(remaining)
        multiplier = self._UNIT_MULTIPLIERS.get(unit_key or "", Decimal("1"))
        rupees = (magnitude * multiplier).quantize(Decimal("1"))

        return MoneyAmount(
            rupees=rupees, magnitude=magnitude, unit_key=unit_key, raw_text=cleaned
        )

    def _extract_unit_key(self, text: str) -> Optional[str]:
        candidates = text.split()
        for token in candidates:
            token_clean = token.strip().strip(".,")
            if not token_clean:
                continue
            if token_clean in self._UNIT_MULTIPLIERS:
                return self._normalise_unit_key(token_clean)
        return None

    @staticmethod
    def _normalise_unit_key(raw: str) -> Optional[str]:
        raw_lower = raw.lower()
        mapping = {
            "crore": {
                "crore",
                "crores",
                "cr",
                "cr.",
                "karod",
                "karor",
                "\u0915\u0930\u094b\u0921",
                "\u0915\u0930\u094b\u095c",
            },
            "lakh": {
                "lakh",
                "lakhs",
                "lac",
                "lacs",
                "\u0932\u093e\u0916",
                "\u0932\u093e\u0916\u094b",
            },
            "thousand": {
                "thousand",
                "thousands",
                "k",
                "hazaar",
                "hazar",
                "\u0939\u091c\u093e\u0930",
                "\u0939\u091c\u093e\u0930\u094b",
            },
            "million": {"million", "millions", "mn", "\u092e\u093f\u0932\u093f\u092f\u0928"},
        }
        for key, alternatives in mapping.items():
            if raw_lower in alternatives:
                return key
        return None

