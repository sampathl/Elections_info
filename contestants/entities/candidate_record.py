"""Dataclasses for election candidate metadata."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class CandidateRecord:
    constituency_id: str
    candidate_id: str
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
    election_year: str = ""

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                sanitized = ""
            elif isinstance(value, str):
                sanitized = value.strip()
            else:
                sanitized = str(value).strip()
            object.__setattr__(self, field.name, sanitized)
