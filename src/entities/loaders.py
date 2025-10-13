"""CSV helpers for constructing candidate records."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from src.entities.candidate_record import CandidateRecord


EXPECTED_COLUMNS = (
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


def iter_candidate_records(path: Path) -> Iterator[CandidateRecord]:
    """Yield ``CandidateRecord`` entries from a CSV file."""

    with Path(path).expanduser().resolve().open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty")
        _validate_columns(reader.fieldnames)
        for row in reader:
            yield _row_to_record(row)


def load_candidate_records(path: Path) -> List[CandidateRecord]:
    """Return all ``CandidateRecord`` entries from the CSV."""

    return list(iter_candidate_records(path))


def _row_to_record(row: Dict[str, object]) -> CandidateRecord:
    return CandidateRecord(
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


def _normalise_value(row: Dict[str, object], key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def _validate_columns(fieldnames: Iterable[str]) -> None:
    missing = [column for column in EXPECTED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(
            "CSV is missing expected columns: " + ", ".join(missing)
        )
