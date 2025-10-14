"""Interfaces and data structures for video overlay text."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Protocol, Sequence, Tuple

from src.entities.candidate_record import CandidateRecord


@dataclass(frozen=True)
class VideoSegmentText:
    """Container for text elements rendered on top of a video segment."""

    primary: str
    secondary: str | None = None
    callouts: Tuple[str, ...] = field(default_factory=tuple)
    duration_hint: float | None = None

    def lines(self) -> Sequence[str]:
        """Return the ordered text lines suitable for on-screen display."""
        items = [self.primary]
        if self.secondary:
            items.append(self.secondary)
        items.extend(self.callouts)
        return tuple(filter(None, items))


class VideoTextFormatter(Protocol):
    """Protocol implemented by locale-specific video text formatters."""

    locale: str

    def segment_texts(self, record: CandidateRecord) -> Dict[str, VideoSegmentText]:
        """Return overlay text keyed by segment identifier."""
        ...
