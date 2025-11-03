"""Interfaces and data structures for video overlay text."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol

from contestants.entities.candidate_record import CandidateRecord


@dataclass(frozen=True)
class VideoSegmentText:
    """Container holding overlay text content for a video segment."""

    text: str


class VideoTextFormatter(Protocol):
    """Protocol implemented by locale-specific video text formatters."""

    locale: str

    def segment_texts(self, record: CandidateRecord) -> Dict[str, VideoSegmentText]:
        """Return overlay text keyed by segment identifier."""
        ...
