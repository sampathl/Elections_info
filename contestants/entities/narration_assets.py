"""Data containers for per-segment narration artefacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from contestants.entities.candidate_record import CandidateRecord
from contestants.video_pipeline.text_generators.base import VideoSegmentText


@dataclass
class SegmentAsset:
    """Holds artefacts for a single narration segment."""

    key: str
    ssml: Optional[str] = None
    text: Optional[str] = None
    audio_path: Optional[Path] = None
    video_path: Optional[Path] = None
    overlay_text: Optional[VideoSegmentText] = None
    overlay_style: Optional[str] = None  # Placeholder for future caption layout presets.

    def is_complete(self) -> bool:
        """Return True when all artefact slots for the segment are populated."""
        return all(
            value is not None
            for value in (self.ssml, self.text, self.audio_path, self.video_path)
        )


@dataclass
class CandidateNarrationAssets:
    """Aggregate per-segment artefacts for a single candidate narration."""

    DEFAULT_SEGMENT_ORDER: ClassVar[Sequence[str]] = (
        "name",
        "party",
        "constituency",
        "age",
        "education",
        "assets",
        "liabilities",
        "criminal_cases",
    )

    record: CandidateRecord
    output_base_dir: Optional[Path] = None
    background_directory: Optional[Path] = None
    locale_directory: Optional[Path] = None
    audio_segments_dir: Optional[Path] = None
    video_segments_dir: Optional[Path] = None
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
        overlay_text: Optional[VideoSegmentText] = None,
        overlay_style: Optional[str] = None,
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
        if overlay_text is not None:
            segment.overlay_text = overlay_text
        if overlay_style is not None:
            segment.overlay_style = overlay_style

    def ordered_segments(self, order: Optional[Sequence[str]] = None) -> List[SegmentAsset]:
        """Return segment assets in the provided order or sensible default."""
        result: List[SegmentAsset] = []
        seen: set[str] = set()

        if order is None:
            order = self.DEFAULT_SEGMENT_ORDER

        for key in order:
            if key in self.segments:
                result.append(self.segments[key])
                seen.add(key)

        for key, segment in self.segments.items():
            if key not in seen:
                result.append(segment)

        return result

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

    def configure_output_paths(self, base_dir: Path, locale: str) -> None:
        """Set the per-candidate output directories."""
        base_dir = base_dir.resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        locale_dir = base_dir / locale
        audio_dir = locale_dir / "audio_segments"
        video_dir = locale_dir / "video_segments"

        locale_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)
        video_dir.mkdir(parents=True, exist_ok=True)

        self.output_base_dir = base_dir
        self.locale_directory = locale_dir
        self.audio_segments_dir = audio_dir
        self.video_segments_dir = video_dir
