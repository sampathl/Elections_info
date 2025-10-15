"""Skeleton pipeline for SSML, audio, and video generation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Sequence

from src.entities.narration_assets import CandidateNarrationAssets, SegmentAsset
from src.audio_pipeline.ssml_generators.factory import CandidateNarratorFactory
from src.audio_pipeline.tts_clients.google_tts_client import (
    DEFAULT_CHIRP3_MODEL,
    select_chirp3_voice,
    synthesize_audio_with_chirp3,
)
from src.entities.candidate_record import CandidateRecord
from src.entities.loaders import iter_candidate_records
from src.video_pipeline.layouts import EnglishVideoLayoutStrategy, HindiVideoLayoutStrategy
from src.video_pipeline.segment_renderer import SegmentVideoRenderer
from src.video_pipeline.text_generators import VideoTextFactory

# TODO: Replace with configurable audio output directory.
AUDIO_OUTPUT_DIRECTORY = Path("tests/audio")


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
        store_full_ssml: bool = False,
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
            if store_full_ssml:
                assets.full_ssml = narrator.ssml_text(
                    assets.record, include_speak_wrapper=wrap_with_speak
                )

    def populate_text(self, assets: CandidateNarrationAssets) -> None:
        """Populate human-readable text for each segment."""
        narrator = CandidateNarratorFactory().create(self.locale)
        segments = narrator.ssml_segments(assets.record)

        for key, fragment in segments.items():
            plain = self._strip_markup(fragment)
            assets.update_segment(key, text=plain)
        full_plain = narrator.ssml_text(
            assets.record, include_speak_wrapper=False
        )
        assets.full_text = self._strip_markup(full_plain)

    def populate_video_text(self, assets: CandidateNarrationAssets) -> None:
        """Populate overlay text used for per-segment video captions."""
        formatter = VideoTextFactory().create(self.locale)
        overlays = formatter.segment_texts(assets.record)

        for key, overlay in overlays.items():
            assets.update_segment(key, overlay_text=overlay)

    def synthesize_audio(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment audio files."""
        AUDIO_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        voice_selection = select_chirp3_voice(self.locale, model=DEFAULT_CHIRP3_MODEL)

        for segment in self.segment_sequence(assets):
            ssml = segment.ssml
            if not ssml:
                continue

            ssml = ssml.strip()
            if not ssml:
                continue

            if not ssml.lstrip().startswith("<speak"):
                ssml = f"<speak>{ssml}</speak>"

            file_stem = self._segment_audio_stem(assets.record.candidate_name, segment.key)
            output_path = AUDIO_OUTPUT_DIRECTORY / f"{file_stem}.mp3"
            synthesize_audio_with_chirp3(
                ssml,
                str(output_path),
                voice_selection,
                self.locale,
            )
            assets.update_segment(segment.key, audio_path=output_path)

    def render_video(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment video clips."""
        if self.locale == "en":
            strategy = EnglishVideoLayoutStrategy()
        elif self.locale == "hi":
            strategy = HindiVideoLayoutStrategy()
        else:
            raise NotImplementedError(
                f"Video rendering not yet implemented for locale '{self.locale}'"
            )

        renderer = SegmentVideoRenderer(layout_strategy=strategy)

        segments = list(self.segment_sequence(assets))
        renderer.render_segments(assets, segments)

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

    def iter_assets_from_csv(
        self,
        csv_path: Path,
        *,
        wrap_with_speak: bool = True,
    ) -> Iterable[CandidateNarrationAssets]:
        """Yield populated assets for each record in the CSV."""

        for record in iter_candidate_records(csv_path):
            assets = self.build_assets(record)
            self.populate_ssml(
                assets,
                wrap_with_speak=wrap_with_speak,
                store_full_ssml=True,
            )
            self.populate_text(assets)
            yield assets

    def combine_text_report(
        self,
        assets_list: Iterable[CandidateNarrationAssets],
    ) -> str:
        """Return combined SSML/text output suitable for a single file."""

        lines: list[str] = []
        for idx, assets in enumerate(assets_list, start=1):
            header = f"## {idx:03d} - {assets.record.candidate_name} ({assets.record.constituency})"
            lines.append(header)
            lines.append("# SSML")
            lines.append(assets.full_ssml or "(no SSML)")
            lines.append("# Text")
            lines.append(assets.full_text or "(no text)")
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _strip_markup(text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"<mark[^>]*?>", "", text)
        cleaned = cleaned.replace("<speak>", "").replace("</speak>", "")
        return cleaned.strip()

    @staticmethod
    def _segment_audio_stem(candidate_name: str, segment_key: str) -> str:
        base = f"{candidate_name}_{segment_key}"
        sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_")
        return sanitized or "segment"
