"""Skeleton pipeline for SSML, audio, and video generation."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from shutil import copy2
from typing import Iterable, List, Sequence, Union

from winners.entities.narration_assets import CandidateNarrationAssets, SegmentAsset
from winners.audio_pipeline.ssml_generators.factory import CandidateNarratorFactory
from winners.audio_pipeline.tts_clients.google_tts_client import (
    DEFAULT_CHIRP3_MODEL,
    select_chirp3_voice,
    synthesize_audio_with_chirp3,
)
from winners.entities.candidate_record import CandidateRecord
from winners.entities.loaders import iter_candidate_records
from winners.video_pipeline.combiner import stitch_videos
from winners.video_pipeline.layouts import (
    EnglishVideoLayoutStrategy,
    HindiVideoLayoutStrategy,
    VideoLayoutStrategy,
)
from winners.video_pipeline.paths import (
    candidate_base_directory,
    choose_background_directory,
    combined_video_directory,
    combined_video_filename,
)
from winners.video_pipeline.utils import sanitize_filename_fragment
from winners.video_pipeline.segment_renderer import SegmentVideoRenderer
from winners.video_pipeline.text_generators import VideoTextFactory
from winners.utils.logging_config import PipelineLoggerAdapter, get_pipeline_logger


class NarrationPipeline:
    """High-level pipeline orchestrator for narration artefacts."""

    def __init__(
        self,
        *,
        locale: str,
        segment_order: Sequence[str] | None = None,
        logger: Union[logging.Logger, PipelineLoggerAdapter, None] = None,
    ) -> None:
        self.locale = locale
        self._segment_order = segment_order
        if logger is None:
            base_logger = get_pipeline_logger(__name__, locale=locale, component="narration")
        elif isinstance(logger, PipelineLoggerAdapter):
            base_logger = logger.bind(locale=locale, component="narration")
        else:
            base_logger = PipelineLoggerAdapter(logger, {"locale": locale, "component": "narration"})
        self._logger = base_logger.bind(segment="-")

    def build_assets(self, record: CandidateRecord) -> CandidateNarrationAssets:
        """Return an empty asset set for the record."""
        stage_logger = self._logger.bind(
            candidate=record.candidate_id or record.candidate_name or "-",
            component="assets",
            segment="-",
        )
        stage_logger.info(
            "Preparing assets for %s (%s)",
            record.candidate_name or "Unknown Candidate",
            record.constituency or "Unknown Constituency",
        )
        assets = CandidateNarrationAssets(record=record)
        base_dir = candidate_base_directory(record)
        assets.configure_output_paths(base_dir, self.locale)
        seed = f"{record.constituency_id}:{record.candidate_id}"
        assets.background_directory = choose_background_directory(self.locale, seed=seed)
        stage_logger.debug("Assets configured under %s", assets.locale_directory)
        return assets

    def populate_ssml(
        self,
        assets: CandidateNarrationAssets,
        wrap_with_speak: bool = True,
        store_full_ssml: bool = False,
    ) -> None:
        """Populate SSML fragments on the provided assets."""
        stage_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="ssml",
            segment="-",
        )
        stage_logger.info("Generating SSML segments")
        narrator = CandidateNarratorFactory().create(self.locale)
        segments = narrator.ssml_segments(assets.record)

        for key, fragment in segments.items():
            if wrap_with_speak and fragment and not fragment.lstrip().startswith("<speak"):
                wrapped = f"<speak>{fragment}</speak>"
            else:
                wrapped = fragment
            assets.update_segment(key, ssml=wrapped)
            stage_logger.debug("SSML segment %s length=%d", key, len(wrapped or ""))
            if store_full_ssml:
                assets.full_ssml = narrator.ssml_text(
                    assets.record, include_speak_wrapper=wrap_with_speak
                )

    def populate_text(self, assets: CandidateNarrationAssets) -> None:
        """Populate human-readable text for each segment."""
        stage_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="text",
            segment="-",
        )
        stage_logger.info("Populating plain text segments")
        narrator = CandidateNarratorFactory().create(self.locale)
        segments = narrator.ssml_segments(assets.record)

        for key, fragment in segments.items():
            plain = self._strip_markup(fragment)
            assets.update_segment(key, text=plain)
            stage_logger.debug("Plain text segment %s length=%d", key, len(plain or ""))
        full_plain = narrator.ssml_text(
            assets.record, include_speak_wrapper=False
        )
        assets.full_text = self._strip_markup(full_plain)

    def populate_video_text(self, assets: CandidateNarrationAssets) -> None:
        """Populate overlay text used for per-segment video captions."""
        stage_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="overlay",
            segment="-",
        )
        stage_logger.info("Generating overlay text for video segments")
        formatter = VideoTextFactory().create(self.locale)
        overlays = formatter.segment_texts(assets.record)

        for key, overlay in overlays.items():
            assets.update_segment(key, overlay_text=overlay)
            stage_logger.debug("Overlay segment %s length=%d", key, len(overlay.text or ""))

    def synthesize_audio(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment audio files."""
        audio_directory = assets.audio_segments_dir
        if audio_directory is None:
            raise ValueError("Audio segments directory has not been configured on assets.")
        audio_directory.mkdir(parents=True, exist_ok=True)
        stage_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="audio",
            segment="-",
        )
        stage_logger.info("Synthesizing audio clips in %s", audio_directory)
        voice_selection = select_chirp3_voice(self.locale, model=DEFAULT_CHIRP3_MODEL)
        stage_logger.debug("Using voice %s", voice_selection)

        for segment in self.segment_sequence(assets):
            segment_logger = stage_logger.bind(segment=segment.key)
            ssml = segment.ssml
            if not ssml:
                segment_logger.warning("Skipping audio synthesis; SSML missing")
                continue

            ssml = ssml.strip()
            if not ssml:
                segment_logger.warning("Skipping audio synthesis; SSML empty after trimming")
                continue

            if not ssml.lstrip().startswith("<speak"):
                ssml = f"<speak>{ssml}</speak>"

            file_stem = self._segment_audio_stem(assets.record.candidate_name, segment.key)
            output_path = audio_directory / f"{file_stem}_{self.locale}.mp3"
            try:
                synthesize_audio_with_chirp3(
                    ssml,
                    str(output_path),
                    voice_selection,
                    self.locale,
                )
            except Exception:
                segment_logger.exception("Audio synthesis failed for segment")
                raise
            segment_logger.info("Audio synthesized at %s", output_path)
            assets.update_segment(segment.key, audio_path=output_path)

    def render_video(self, assets: CandidateNarrationAssets) -> None:
        """Generate per-segment video clips."""
        video_directory = assets.video_segments_dir
        if video_directory is None:
            raise ValueError("Video segments directory has not been configured on assets.")

        background_directory = assets.background_directory
        stage_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="video",
            segment="-",
        )
        stage_logger.info("Rendering video segments in %s", video_directory)

        if self.locale == "en":
            strategy = EnglishVideoLayoutStrategy(
                background_directory=background_directory,
                output_directory=video_directory,
            )
        elif self.locale == "hi":
            strategy = HindiVideoLayoutStrategy(
                background_directory=background_directory,
                output_directory=video_directory,
            )
        else:
            raise NotImplementedError(
                f"Video rendering not yet implemented for locale '{self.locale}'"
            )

        renderer = SegmentVideoRenderer(
            layout_strategy=strategy,
            logger=self._logger.bind(
                candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
                component="segment_renderer",
                segment="-",
            ),
        )

        segments = list(self.segment_sequence(assets))
        render_results = renderer.render_segments(assets, segments)
        stage_logger.info("Rendered %d segment clip(s)", len(render_results))

        video_paths = [segment.video_path for segment in segments if segment.video_path]
        if not video_paths:
            stage_logger.warning("No segment videos produced; skipping stitching")
            assets.stitched_video_path = None
            self._log_segment_summary(assets)
            return

        stitched_output_path = self._default_stitched_video_path(assets, strategy)
        stitched_output_path.parent.mkdir(parents=True, exist_ok=True)

        stitch_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="stitch",
            segment="stitched",
        )
        try:
            stitch_videos(
                video_paths,
                stitched_output_path,
                fps=strategy.preferred_fps(),
                logger=stitch_logger,
            )
        except Exception:
            stitch_logger.exception("Failed to stitch rendered segments")
            raise
        stitch_logger.info("Stitched video ready at %s", stitched_output_path)
        assets.stitched_video_path = stitched_output_path

        combined_dir = combined_video_directory(assets.record, self.locale)
        combined_filename = combined_video_filename(assets.record, self.locale, stitched_output_path)
        combined_path = combined_dir / combined_filename
        try:
            copy2(stitched_output_path, combined_path)
        except Exception:
            stitch_logger.exception("Failed to copy stitched video to combined directory")
        else:
            stitch_logger.info("Copied stitched video to %s", combined_path)

        self._log_segment_summary(assets)

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
            return assets.ordered_segments()
        return [assets.ensure_segment(key) for key in order]

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

    def _default_stitched_video_path(
        self,
        assets: CandidateNarrationAssets,
        strategy: VideoLayoutStrategy,
    ) -> Path:
        candidate_fragment = sanitize_filename_fragment(
            assets.record.candidate_name,
            allow_unicode=(self.locale == "hi"),
        )
        filename = f"{candidate_fragment}_{self.locale}_stitched.mp4"
        base_directory = assets.locale_directory or strategy.output_directory
        base_directory.mkdir(parents=True, exist_ok=True)
        return base_directory / filename

    def _log_segment_summary(self, assets: CandidateNarrationAssets) -> None:
        summary_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            component="summary",
            segment="-",
        )
        summary = assets.summary()
        if not summary:
            summary_logger.info("No segments available for summary logging")
            return
        formatted = ", ".join(
            f"{key}={'ok' if value else 'missing'}"
            for key, value in summary.items()
        )
        summary_logger.info("Segment completeness: %s", formatted)
