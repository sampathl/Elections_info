"""Dataclasses for election candidate metadata."""

from __future__ import annotations

from dataclasses import dataclass


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
