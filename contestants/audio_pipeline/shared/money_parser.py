"""Locale-aware helpers for parsing textual currency amounts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Iterable, Mapping, Optional, Tuple

from winners.audio_pipeline.localizers.money import MoneyAmount

_NUMERIC_PATTERN = re.compile(r"[-+]?[0-9]+(?:[.,][0-9]+)?")
_BASE_UNIT_MULTIPLIERS = {
    "crore": Decimal("10000000"),
    "lakh": Decimal("100000"),
    "thousand": Decimal("1000"),
    "million": Decimal("1000000"),
}


def parse_money_amount(
    primary: str,
    fallback: str = "",
    *,
    aliases: Mapping[str, Iterable[str]],
    currency_tokens: Iterable[str],
) -> Optional[MoneyAmount]:
    """Return a `MoneyAmount` parsed from textual input.

    Args:
        primary: Preferred text to parse.
        fallback: Secondary text to parse when the primary fails.
        aliases: Mapping of canonical unit names (e.g., "crore")
            to iterables of aliases. Include the canonical label if desired.
        currency_tokens: Strings to strip before numeric parsing (e.g., "rs", "₹").
    """
    for candidate in (primary, fallback):
        amount = _parse_single(candidate, aliases, tuple(currency_tokens))
        if amount is not None:
            return amount
    return None


def _parse_single(
    value: str,
    aliases: Mapping[str, Iterable[str]],
    currency_tokens: Tuple[str, ...],
) -> Optional[MoneyAmount]:
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned or cleaned.lower() == "nan":
        return None

    normalised = cleaned.lower()
    for token in currency_tokens:
        normalised = normalised.replace(token.lower(), "")

    numeric_match = _NUMERIC_PATTERN.search(normalised.replace(",", ""))
    if not numeric_match:
        return None

    try:
        magnitude = Decimal(numeric_match.group(0))
    except InvalidOperation:
        return None

    remaining = _NUMERIC_PATTERN.sub("", normalised)
    unit_key = _extract_unit_key(remaining, aliases)
    multiplier = _unit_multiplier(unit_key)
    rupees = (magnitude * multiplier).quantize(Decimal("1"))

    return MoneyAmount(
        rupees=rupees,
        magnitude=magnitude,
        unit_key=unit_key,
        raw_text=cleaned,
    )


def _extract_unit_key(
    residue: str, aliases: Mapping[str, Iterable[str]]
) -> Optional[str]:
    #print(aliases)
    
    lookup = _alias_lookup(_freeze_aliases(aliases))
    for token in residue.split():
        canonical = lookup.get(token.strip(".,").lower())
        if canonical is not None:
            return canonical
    return None


def _unit_multiplier(unit_key: Optional[str]) -> Decimal:
    if unit_key is None:
        return Decimal("1")
    return _BASE_UNIT_MULTIPLIERS.get(unit_key, Decimal("1"))


@lru_cache(maxsize=None)
def _alias_lookup(
    frozen_aliases: Tuple[Tuple[str, Tuple[str, ...]], ...]
) -> Mapping[str, str]:
    lookup: dict[str, str] = {}
    for canonical, variations in frozen_aliases:
        canonical_lower = canonical.lower()
        lookup.setdefault(canonical_lower, canonical)
        for alias in variations:
            lookup.setdefault(alias.lower(), canonical)
    return lookup


def _freeze_aliases(
    aliases: Mapping[str, Iterable[str]]
) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
    return tuple(
        (canonical, tuple(variations))
        for canonical, variations in aliases.items()
    )
