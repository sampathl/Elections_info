"""CSV loader and entities for election candidate metadata with SSML helpers."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import inflect

from src.audio_pipeline.phonetics.phonetics_generator import (
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