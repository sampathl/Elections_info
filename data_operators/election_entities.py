"""CSV loader and entities for election candidate metadata with SSML helpers."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import inflect

from data_operators.phonetics_generator import (
    generate_phoneme_string,
    generate_ssml_phonetics,
    generate_ssml_phonetics_native,
)


logger = logging.getLogger(__name__)
p = inflect.engine()


EXPECTED_COLUMNS: Sequence[str] = (
    "Constituency",
    "Election_Type",
    "Candidate_name",
    "Party",
    "Criminal_Cases",
    "Education",
    "education_details",
    "age",
    "total_assets",
    "assets_description",
    "total_liabilities",
    "liabilities_description",
    "voter_info",
    "url",
)


@dataclass
class CandidateRecord:
    constituency: str
    election_type: str
    candidate_name: str
    party: str
    criminal_cases: str
    education: str
    education_details: str
    age: str
    total_assets: str
    assets_description: str
    total_liabilities: str
    liabilities_description: str
    voter_info: str
    url: str


class CandidateEntity(CandidateRecord):
    """Candidate record augmented with phoneme and SSML helpers."""

    def _phoneme_for_value(
        self,
        value: str,
        *,
        joiner: str = " ",
        transcriber: Optional[object] = None,
    ) -> str:
        text = value.strip() if value else ""
        if not text:
            return ""
        if transcriber is not None:
            logger.debug(
                "Transcriber parameter ignored while generating phoneme string for '%s'",
                text,
            )
        return generate_phoneme_string(text, joiner=joiner)

    def _ssml_for_value(
        self,
        value: str,
        *,
        locale: str = "en",
        transcriber: Optional[object] = None,
    ) -> str:
        text = value.strip() if value else ""
        if not text:
            return ""
        if transcriber is not None:
            logger.debug(
                "Transcriber parameter ignored while generating SSML for '%s'",
                text,
            )
        if locale.lower() == "hi":
            return generate_ssml_phonetics_native(text)
        return generate_ssml_phonetics(text)

    def phoneme_for_candidate(
        self,
        *,
        joiner: str = " ",
        transcriber: Optional[object] = None,
    ) -> str:
        """Return phoneme string for `candidate_name`."""

        return self._phoneme_for_value(
            self.candidate_name, joiner=joiner, transcriber=transcriber
        )

    def phoneme_for_party(
        self,
        *,
        joiner: str = " ",
        transcriber: Optional[object] = None,
    ) -> str:
        """Return phoneme string for `party`."""

        return self._phoneme_for_value(self.party, joiner=joiner, transcriber=transcriber)

    def phoneme_for_constituency(
        self,
        *,
        joiner: str = " ",
        transcriber: Optional[object] = None,
    ) -> str:
        """Return phoneme string for `constituency`."""

        return self._phoneme_for_value(
            self.constituency, joiner=joiner, transcriber=transcriber
        )

    # --- SSML segment builders ---

    def _describe_candidate_name(
        self, *, transcriber: Optional[object] = None
    ) -> str:
        name_ssml = self._ssml_for_value(self.candidate_name, transcriber=transcriber)
        if not name_ssml:
            return ""
        return (
            f" Candidate name: {name_ssml}<mark name=\"name\"/>"
        )

    def _describe_party(
        self, *, transcriber: Optional[object] = None
    ) -> str:
        party_text = self.party.strip()
        if not party_text:
            return ""

        party_ssml = self._ssml_for_value(party_text, transcriber=transcriber)
        if party_text.lower() == "independent":
            descriptor = "is an Independent candidate"
        elif "party" in party_text.lower():
            descriptor = f"is a member of the {party_ssml}"
        else:
            descriptor = f"is a member of the {party_ssml} party"

        return f", {descriptor} <mark name=\"party\"/>"

    def _describe_constituency(
        self, *, transcriber: Optional[object] = None
    ) -> str:
        constituency_ssml = self._ssml_for_value(
            self.constituency, transcriber=transcriber
        )
        if not constituency_ssml:
            return ""
        return (
            f", is contesting for {constituency_ssml} seat"
            "<mark name=\"constituency\"/>"
        )

    def _describe_age(self) -> str:
        age_text = self.age.strip()
        if not age_text:
            return ""
        return f", at the age of {age_text}<mark name=\"age\"/>"

    def _describe_education(self) -> str:
        education_level = self.education.strip()
        descriptions = {
            "Doctorate": ", holds a Doctorate degree<mark name=\"education\"/>",
            "Graduate": ", holds a Graduate degree<mark name=\"education\"/>",
            "Post Graduate": ", holds a Post Graduate degree <mark name=\"education\"/>",
            "10th Pass": ", has completed secondary education<mark name=\"education\"/>",
            "12th Pass": ", has completed higher secondary education<mark name=\"education\"/>",
            "Graduate Professional": ", is a Graduate Professional<mark name=\"education\"/>",
            "5th Pass": ", with primary education<mark name=\"education\"/>",
            "8th Pass": ", has completed middle school<mark name=\"education\"/>",
            "Others": ", has other educational qualifications<mark name=\"education\"/>",
            "Illiterate": ", is illiterate <mark name=\"age\"/>",
            "Literate": ",  is literate but with unspecified formal education<mark name=\"education\"/>",
            "Not Given": ", has unspecified educational background<mark name=\"education\"/>",
        }

        detail_suffix = ""
        if self.education_details.strip():
            detail_suffix = f" ({self.education_details.strip()})"

        if education_level in descriptions:
            base = descriptions[education_level]
            if detail_suffix:
                base = base.replace("<mark name=\"education\"/>", f"{detail_suffix}<mark name=\"education\"/>")
            return base

        if not education_level:
            return " <mark name=\"education\"/>"

        return f", has {education_level}{detail_suffix}<mark name=\"education\"/>"

    @staticmethod
    def _safe_int(value: str) -> Optional[int]:
        if not value:
            return None
        numeric = re.sub(r"[^0-9]", "", value)
        if not numeric:
            return None
        try:
            return int(numeric)
        except ValueError:
            return None

    def _describe_criminal_cases(self) -> str:
        numeric_value = self._safe_int(self.criminal_cases.strip())
        if numeric_value is None:
            return ", with an unknown legal standing<mark name=\"criminal_cases\"/> "
        if numeric_value == 0:
            return ", with no criminal cases on record<mark name=\"criminal_cases\"/>"
        if numeric_value == 1:
            return ", with 1 criminal case on record<mark name=\"criminal_cases\"/>"
        return (
            f", <google:style name=\"apologetic\">with {numeric_value} criminal cases on record"
            "</google:style><mark name=\"criminal_cases\"/>"
        )

    def _convert_money_to_words(
        self,
        amount_words: str,
        amount_numeric: str,
        amount_type: str,
    ) -> str:
        amount_type = amount_type.lower()
        amount_words_clean = amount_words.strip()

        amount_in_words: Optional[str]
        if amount_words_clean and not amount_words_clean.replace(" ", "").isdigit() and amount_words_clean.lower() != "nan":
            amount_in_words = amount_words_clean
        else:
            numeric_value = self._safe_int(amount_numeric)
            if numeric_value is None:
                return (
                    f", declared {amount_type} with unspecified value"
                    f" <mark name=\"{amount_type}\"/>"
                )
            if numeric_value == 0:
                return f", no declared {amount_type} <mark name=\"{amount_type}\"/>"

            amount_in_words = p.number_to_words(numeric_value)
            lowered = amount_in_words.lower()
            if "crore" in lowered:
                unit = "crore"
            elif "lakh" in lowered or "lac" in lowered:
                unit = "lakh"
            elif "thou" in lowered:
                unit = "thousand"
            else:
                unit = ""
            if unit:
                amount_in_words = p.plural(unit, numeric_value)

        if amount_type == "assets":
            return (
                f", declared assets valued at {amount_in_words} "
                f"<mark name=\"{amount_type}\"/>"
            )
        if amount_type == "liabilities":
            return (
                f", declared liabilities amounting to {amount_in_words} "
                f"<mark name=\"{amount_type}\"/>"
            )

        return (
            f", declared {amount_in_words} of {amount_type} "
            f"<mark name=\"{amount_type}\"/>"
        )

    def _describe_assets(self) -> str:
        if not self.total_assets.strip() and not self.assets_description.strip():
            return ""
        return self._convert_money_to_words(
            self.assets_description,
            self.total_assets,
            "assets",
        )

    def _describe_liabilities(self) -> str:
        if not self.total_liabilities.strip() and not self.liabilities_description.strip():
            return ""
        return self._convert_money_to_words(
            self.liabilities_description,
            self.total_liabilities,
            "liabilities",
        )

    def ssml_segments(
        self, *, transcriber: Optional[object] = None
    ) -> Dict[str, str]:
        """Return SSML fragments keyed by segment name."""

        segments = {
            "name": self._describe_candidate_name(transcriber=transcriber),
            "party": self._describe_party(transcriber=transcriber),
            "constituency": self._describe_constituency(transcriber=transcriber),
            "age": self._describe_age(),
            "education": self._describe_education(),
            "criminal_cases": self._describe_criminal_cases(),
            "assets": self._describe_assets(),
            "liabilities": self._describe_liabilities(),
        }
        logger.debug("SSML segments generated: %s", segments)
        return segments

    def ssml_text(
        self,
        *,
        transcriber: Optional[object] = None,
        include_speak_wrapper: bool = True,
    ) -> str:
        """Return a full SSML string ready for TTS generation."""

        segments = self.ssml_segments(transcriber=transcriber)
        body = "".join(
            [
                segments.get("name", ""),
                segments.get("party", ""),
                segments.get("constituency", ""),
                segments.get("age", ""),
                segments.get("education", ""),
                segments.get("criminal_cases", ""),
            ]
        )

        assets = segments.get("assets", "")
        liabilities = segments.get("liabilities", "")

        assets_fragment = assets.lstrip(", ") if assets else ""
        liabilities_fragment = liabilities.lstrip(", ") if liabilities else ""

        if assets_fragment:
            body += f", has {assets_fragment}"

        if liabilities_fragment:
            if assets_fragment:
                body += f" and {liabilities_fragment}"
            else:
                body += f", has {liabilities_fragment}"

        if include_speak_wrapper:
            return f"<speak>{body}</speak>"
        return body


def _validate_columns(fieldnames: Iterable[str]) -> None:
    missing = [column for column in EXPECTED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(
            "CSV is missing expected columns: " + ", ".join(missing)
        )


def _iter_candidate_rows(path: Path) -> Iterator[dict]:
    with path.open(newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty")
        _validate_columns(reader.fieldnames)
        for row in reader:
            yield row


def _normalise_value(row: dict, key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def _row_to_entity(row: dict) -> CandidateEntity:
    return CandidateEntity(
        constituency=_normalise_value(row, "Constituency"),
        election_type=_normalise_value(row, "Election_Type"),
        candidate_name=_normalise_value(row, "Candidate_name"),
        party=_normalise_value(row, "Party"),
        criminal_cases=_normalise_value(row, "Criminal_Cases"),
        education=_normalise_value(row, "Education"),
        education_details=_normalise_value(row, "education_details"),
        age=_normalise_value(row, "age"),
        total_assets=_normalise_value(row, "total_assets"),
        assets_description=_normalise_value(row, "assets_description"),
        total_liabilities=_normalise_value(row, "total_liabilities"),
        liabilities_description=_normalise_value(row, "liabilities_description"),
        voter_info=_normalise_value(row, "voter_info"),
        url=_normalise_value(row, "url"),
    )


def load_candidates_from_csv(path: Path) -> List[CandidateEntity]:
    """Read candidate entities from the provided CSV path."""

    resolved = Path(path).expanduser().resolve()
    return [_row_to_entity(row) for row in _iter_candidate_rows(resolved)]


__all__ = [
    "CandidateRecord",
    "CandidateEntity",
    "EXPECTED_COLUMNS",
    "load_candidates_from_csv",
]


if __name__ == "__main__":
    sample_row = {
        "Constituency": "AGIAON (SC)",
        "Election_Type": "General",
        "Candidate_name": "Manoj Manzil",
        "Party": "CPI(ML)(L)",
        "Criminal_Cases": "30",
        "Education": "Graduate",
        "education_details": "B.A. from H.D. Jain College, Ara in 2015",
        "age": "36",
        "total_assets": "316500",
        "assets_description": "3 Lacs",
        "total_liabilities": "",
        "liabilities_description": "",
        "voter_info": "196-Tarari  (Bihar) constituency, at Serial no 619  in Part no   140",
        "url": "https://www.myneta.info/bihar2020/candidate.php?candidate_id=9784",
    }

    entity = _row_to_entity(sample_row)
    print("Candidate Entity:")
    print(entity)
    print("\nPhonemes:")
    print(" - Candidate:", entity.phoneme_for_candidate())
    print(" - Party:", entity.phoneme_for_party())
    print(" - Constituency:", entity.phoneme_for_constituency())
    print("\nSSML Segments:")
    for key, value in entity.ssml_segments().items():
        print(f" {key}: {value}")
    print("\nFull SSML:")
    print(entity.ssml_text())
