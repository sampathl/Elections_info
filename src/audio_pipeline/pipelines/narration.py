"""Skeleton pipeline for SSML, audio, and video generation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from src.audio_pipeline.narration_assets import CandidateNarrationAssets, SegmentAsset
from src.audio_pipeline.ssml_generators.factory import CandidateNarratorFactory
from src.entities.candidate_record import CandidateRecord


class NarrationPipeline:
    """High-level pipeline orchestrator for narration artefacts."""

    def __init__(self, *, locale: str, segment_order: Sequence[str] | None = None) -> None:
        self.locale = locale
        self._segment_order = segment_order

    def build_assets(self, record: CandidateRecord) -> CandidateNarrationAssets:
        """Return an empty asset set for the record."""
        return CandidateNarrationAssets(record=record)

    def populate_ssml(
        self,
        assets: CandidateNarrationAssets,
        wrap_with_speak: bool = True,
    ) -> None:
        """Populate SSML fragments on the provided assets."""
        narrator = CandidateNarratorFactory().create(self.locale)
        segments = narrator.ssml_segments(assets.record)

        for key, fragment in segments.items():
            if wrap_with_speak and fragment and not fragment.lstrip().startswith("<speak"):
                wrapped = f"<speak>{fragment}</speak>"
            else:
                wrapped = fragment
            assets.update_segment(key, ssml=wrapped)

    def populate_text(self, assets: CandidateNarrationAssets) -> None:
        """Populate human-readable text for each segment."""
        # To be implemented: derive plain narration text from SSML or formatters.
        raise NotImplementedError

    def synthesize_audio(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment audio files."""
        # To be implemented: call TTS client and store paths in `SegmentAsset`.
        raise NotImplementedError

    def render_video(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment video clips."""
        # To be implemented: pair audio with visuals and store clip paths.
        raise NotImplementedError

    def stitch_audio(self, assets: CandidateNarrationAssets, output_path: Path) -> None:
        """Combine per-segment audio into a single timeline."""
        # To be implemented: combine audio clips and update `stitched_audio_path`.
        raise NotImplementedError

    def stitch_video(self, assets: CandidateNarrationAssets, output_path: Path) -> None:
        """Combine per-segment video clips into a single render."""
        # To be implemented: combine video clips and update `stitched_video_path`.
        raise NotImplementedError

    def segment_sequence(self, assets: CandidateNarrationAssets) -> Iterable[SegmentAsset]:
        """Yield segments in the configured order."""
        order = self._segment_order
        if order is None:
            return assets.segments.values()
        return (assets.ensure_segment(key) for key in order)
