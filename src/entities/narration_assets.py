"""Data containers for per-segment narration artefacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from src.entities.candidate_record import CandidateRecord


@dataclass
class SegmentAsset:
    """Holds artefacts for a single narration segment."""

    key: str
    ssml: Optional[str] = None
    text: Optional[str] = None
    audio_path: Optional[Path] = None
    video_path: Optional[Path] = None

    def is_complete(self) -> bool:
        """Return True when all artefact slots for the segment are populated."""
        return all(
            value is not None
            for value in (self.ssml, self.text, self.audio_path, self.video_path)
        )


@dataclass
class CandidateNarrationAssets:
    """Aggregate per-segment artefacts for a single candidate narration."""

    record: CandidateRecord
    segments: MutableMapping[str, SegmentAsset] = field(default_factory=dict)
    full_ssml: Optional[str] = None
    full_text: Optional[str] = None
    stitched_audio_path: Optional[Path] = None
    stitched_video_path: Optional[Path] = None

    def ensure_segment(self, key: str) -> SegmentAsset:
        """Return the segment asset, creating an empty stub if needed."""
        if key not in self.segments:
            self.segments[key] = SegmentAsset(key=key)
        return self.segments[key]

    def update_segment(
        self,
        key: str,
        *,
        ssml: Optional[str] = None,
        text: Optional[str] = None,
        audio_path: Optional[Path] = None,
        video_path: Optional[Path] = None,
    ) -> None:
        """Store artefacts for the specified segment."""
        segment = self.ensure_segment(key)
        if ssml is not None:
            segment.ssml = ssml
        if text is not None:
            segment.text = text
        if audio_path is not None:
            segment.audio_path = audio_path
        if video_path is not None:
            segment.video_path = video_path

    def ordered_segments(self, order: Optional[Sequence[str]] = None) -> List[SegmentAsset]:
        """Return segment assets in the provided order or dictionary order."""
        if order is None:
            return list(self.segments.values())
        return [self.ensure_segment(key) for key in order]

    def iter_completed_segments(self) -> Iterable[SegmentAsset]:
        """Yield segments where every artefact slot has been filled."""
        for segment in self.segments.values():
            if segment.is_complete():
                yield segment

    def summary(self) -> Mapping[str, bool]:
        """Return completeness status keyed by segment name."""
        return {key: segment.is_complete() for key, segment in self.segments.items()}

    def reset_outputs(self) -> None:
        """Clear stitched output locations."""
        self.stitched_audio_path = None
        self.stitched_video_path = None
