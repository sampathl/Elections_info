"""Localized election narration with pluggable formatting and phonetics.

This module demonstrates one way to restructure narration logic so that new
languages can be introduced without modifying the underlying data model. The
design centres around a few key abstractions:

* ``LocaleFormatter`` keeps language-specific phrasing, numeric formatting, and
  SSML quirks in one place.
* ``MoneyParser`` normalises free-form financial strings into a structured
  representation that formatters can render in their preferred style.
* ``LocalizedNarrator`` composes segments using a formatter and optional
  phonetics provider, returning both per-segment SSML and the full narration.
* ``CandidateNarratorFactory`` follows the Strategy/Factory patterns to supply
  narrator instances for a requested locale, ready to plug into existing
  workflows.

The module is additive: it imports ``CandidateEntity`` from ``election_entities``
but does not modify that source file.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, Protocol

try:  # pragma: no cover - support running inside and outside the package
    from .election_entities import CandidateEntity
except ImportError:  # pragma: no cover - fallback for direct execution
    from election_entities import CandidateEntity  # type: ignore

try:  # Optional phonetics integration
    from .phonetics_engine import (
        PhoneticsProvider,
        TranscriberRegistry,
        TransliterationUnavailable,
    )
except ImportError:  # pragma: no cover - phonetics module may be absent
    PhoneticsProvider = None  # type: ignore
    TranscriberRegistry = None  # type: ignore
    TransliterationUnavailable = RuntimeError  # type: ignore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Money parsing helpers
# ---------------------------------------------------------------------------


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

    # Inject proper Devanagari spellings while keeping the mapping ASCII-only
    _DEVANAGARI_ALIASES = {
        "crore": {"\u0915\u0930\u094b\u0921", "\u0915\u0930\u094b\u095c"},
        "lakh": {"\u0932\u093e\u0916", "\u0932\u093e\u0916\u094b"},
        "thousand": {"\u0939\u091c\u093e\u0930", "\u0939\u091c\u093e\u0930\u094b"},
        "million": {"\u092e\u093f\u0932\u093f\u092f\u0928"},
    }

    def __init__(self) -> None:
        # Populate unit lookup with hinge/Devanagari aliases.
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

        return MoneyAmount(rupees=rupees, magnitude=magnitude, unit_key=unit_key, raw_text=cleaned)

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
            "crore": {"crore", "crores", "cr", "cr.", "karod", "karor", "\u0915\u0930\u094b\u0921", "\u0915\u0930\u094b\u095c"},
            "lakh": {"lakh", "lakhs", "lac", "lacs", "\u0932\u093e\u0916", "\u0932\u093e\u0916\u094b"},
            "thousand": {"thousand", "thousands", "k", "hazaar", "hazar", "\u0939\u091c\u093e\u0930", "\u0939\u091c\u093e\u0930\u094b"},
            "million": {"million", "millions", "mn", "\u092e\u093f\u0932\u093f\u092f\u0928"},
        }
        for key, alternatives in mapping.items():
            if raw_lower in alternatives:
                return key
        return None


# ---------------------------------------------------------------------------
# Locale-specific formatting
# ---------------------------------------------------------------------------


class LocaleFormatter(Protocol):
    locale: str

    def name_segment(self, name_ssml: str, entity: CandidateEntity) -> str:
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
    mark_name = 'name'
    mark_party = 'party'
    mark_constituency = 'constituency'
    mark_age = 'age'
    mark_education = 'education'
    mark_criminal = 'criminal_cases'
    mark_assets = 'assets'
    mark_liabilities = 'liabilities'

    def _with_mark(self, text: str, mark: str) -> str:
        if not text:
            return ""
        return f"{text}<mark name=\"{mark}\"/>"


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


_DEVANAGARI_DIGITS = str.maketrans("0123456789", "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f")


class EnglishNarrationFormatter(_FormatterBase, LocaleFormatter):
    locale = "en"

    def name_segment(self, name_ssml: str, entity: CandidateEntity) -> str:
        return self._with_mark(f" Candidate name: {name_ssml}", self.mark_name)

    def party_segment(self, party_text: str, party_ssml: str) -> str:
        if not party_text:
            return ""
        lower = party_text.lower()
        if lower == "independent":
            descriptor = "is an independent candidate"
        elif "party" in lower:
            descriptor = f"is a member of the {party_ssml}"
        else:
            descriptor = f"is a member of the {party_ssml} party"
        return self._with_mark(f", {descriptor}", self.mark_party)

    def constituency_segment(self, constituency_ssml: str) -> str:
        if not constituency_ssml:
            return ""
        return self._with_mark(", contesting for the {constituency} seat".format(constituency=constituency_ssml), self.mark_constituency)

    def age_segment(self, age_text: str) -> str:
        if not age_text:
            return ""
        return self._with_mark(f", aged {age_text}", self.mark_age)

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
        base = descriptions.get(education_level.strip(), "has {education} education".format(education=education_level or "unspecified"))
        suffix = f" ({details})" if details else ""
        return self._with_mark(f", {base}{suffix}", self.mark_education)

    def criminal_segment(self, criminal_text: str) -> str:
        if criminal_text == "unknown":
            phrase = "legal standing is unknown"
        elif criminal_text == "0":
            phrase = "has no criminal cases on record"
        elif criminal_text == "1":
            phrase = "has one criminal case on record"
        else:
            phrase = f"has {criminal_text} criminal cases on record"
        return self._with_mark(f", {phrase}", self.mark_criminal)

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
            phrase = "assets with unspecified value"
        elif amount.rupees == 0:
            phrase = "no assets declared"
        else:
            phrase = f"assets valued at {self._numeric_phrase(amount)}"
        return self._with_mark(phrase, self.mark_assets)

    def liabilities_segment(self, amount: Optional[MoneyAmount]) -> str:
        if amount is None:
            phrase = "liabilities with unspecified value"
        elif amount.rupees == 0:
            phrase = "no liabilities declared"
        else:
            phrase = f"liabilities amounting to {self._numeric_phrase(amount)}"
        return self._with_mark(phrase, self.mark_liabilities)

    def combine_financial_segments(self, assets: str, liabilities: str) -> str:
        fragments = [fragment for fragment in (assets, liabilities) if fragment]
        if not fragments:
            return ""
        joined = " and ".join(fragments)
        return f", {joined}"


class HindiNarrationFormatter(_FormatterBase, LocaleFormatter):
    locale = "hi"

    def name_segment(self, name_ssml: str, entity: CandidateEntity) -> str:
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
        base = mapping.get(education_level.strip(), f"{education_level or 'ashankit shiksha'}")
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
            phrase = f"{criminal_text.translate(_DEVANAGARI_DIGITS)} apradhik mamle darj hain"
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


# ---------------------------------------------------------------------------
# Narrator implementation
# ---------------------------------------------------------------------------


class CandidateNarrator(Protocol):
    def ssml_segments(self, entity: CandidateEntity) -> Dict[str, str]:
        ...

    def ssml_text(
        self,
        entity: CandidateEntity,
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
        money_parser: MoneyParser,
        phonetics: Optional[PhoneticsProvider] = None,
    ) -> None:
        self._formatter = formatter
        self._money_parser = money_parser
        self._phonetics = phonetics

    def _ssml_value(self, text: str) -> str:
        if not text:
            return ""
        if self._phonetics is None:
            return text
        try:
            return self._phonetics.to_ssml(text)
        except Exception as exc:  # pragma: no cover - optional dependency at runtime
            logger.warning("Phonetics generation failed for '%s': %s", text, exc)
            return text

    def _criminal_value(self, criminal_cases: str) -> str:
        stripped = criminal_cases.strip()
        if not stripped:
            return "unknown"
        numeric_only = re.sub(r"[^0-9]", "", stripped)
        return numeric_only or "unknown"

    def ssml_segments(self, entity: CandidateEntity) -> Dict[str, str]:
        assets_amount = self._money_parser.parse(
            entity.assets_description, entity.total_assets
        )
        liabilities_amount = self._money_parser.parse(
            entity.liabilities_description, entity.total_liabilities
        )

        name_segment = self._formatter.name_segment(
            self._ssml_value(entity.candidate_name), entity
        )
        party_segment = self._formatter.party_segment(
            entity.party.strip(), self._ssml_value(entity.party)
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
        entity: CandidateEntity,
        *,
        include_speak_wrapper: bool = True,
    ) -> str:
        segments = self.ssml_segments(entity)
        ordered_keys = ["name", "party", "constituency", "age", "education", "criminal_cases"]
        body = "".join(segments.get(key, "") for key in ordered_keys)

        financial = self._formatter.combine_financial_segments(
            segments.get("assets", ""), segments.get("liabilities", "")
        )
        body += financial

        if include_speak_wrapper:
            return f"<speak>{body}</speak>"
        return body


# ---------------------------------------------------------------------------
# Factory and convenience helpers
# ---------------------------------------------------------------------------


class CandidateNarratorFactory:
    """Factory delivering narrator instances for a given locale."""

    def __init__(
        self,
        *,
        money_parser: Optional[MoneyParser] = None,
        transcriber_registry: Optional[TranscriberRegistry] = None,
    ) -> None:
        self._money_parser = money_parser or MoneyParser()
        if transcriber_registry is not None:
            self._registry = transcriber_registry
        elif TranscriberRegistry is not None:
            self._registry = TranscriberRegistry()
        else:
            self._registry = None

    def _resolve_phonetics(self, locale: str) -> Optional[PhoneticsProvider]:
        if PhoneticsProvider is None or self._registry is None:
            return None

        # Reuse Hindi phonetics for both English and Hindi narrations because the
        # names are Romanised variants of Indic languages and benefit from the
        # same transliteration pipeline.
        locale_to_config = {
            "en": ("hi", "Deva"),
            "hi": ("hi", "Deva"),
        }

        config = locale_to_config.get(locale)
        if not config:
            return None

        lang, script = config
        try:
            return self._registry.get(lang, script)
        except TransliterationUnavailable as exc:  # pragma: no cover
            logger.info("Phonetics unavailable for %s-%s: %s", lang, script, exc)
            return None

    def create(self, locale: str) -> LocalizedNarrator:
        if locale == "en":
            formatter: LocaleFormatter = EnglishNarrationFormatter()
        elif locale == "hi":
            formatter = HindiNarrationFormatter()
        else:
            raise ValueError(f"Unsupported locale '{locale}'")

        phonetics = self._resolve_phonetics(locale)
        return LocalizedNarrator(
            formatter=formatter,
            money_parser=self._money_parser,
            phonetics=phonetics,
        )


# ---------------------------------------------------------------------------
# Demonstration CLI (optional)
# ---------------------------------------------------------------------------


if __name__ == "__main__":  # pragma: no cover - manual testing helper
    import json

    entity = CandidateEntity(
        constituency="AGIAON (SC)",
        election_type="General",
        candidate_name="Manoj Manzil",
        party="CPI(ML)(L)",
        criminal_cases="30",
        education="Graduate",
        education_details="B.A. from H.D. Jain College, Ara in 2015",
        age="36",
        total_assets="316500",
        assets_description="3 Lakh",
        total_liabilities="10000",
        liabilities_description="10 Thousand",
        voter_info="196-Tarari (Bihar) constituency, at Serial no 619 in Part no 140",
        url="https://www.myneta.info/bihar2020/candidate.php?candidate_id=9784",
    )
    factory = CandidateNarratorFactory(transcriber_registry=TranscriberRegistry() if TranscriberRegistry else None)
    for locale in ("en", "hi"):
        narrator = factory.create(locale)
        print(f"Locale: {locale}")
        segments = narrator.ssml_segments(entity)
        print(json.dumps(segments, indent=2, ensure_ascii=False))
        print(narrator.ssml_text(entity))
        print("-" * 40)
