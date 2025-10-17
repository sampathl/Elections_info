"""English locale layout strategy for video segments."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Sequence, Tuple

from src.entities.narration_assets import CandidateNarrationAssets, SegmentAsset

from .base import TextLayerSpec, VideoLayoutStrategy

__all__ = ["EnglishVideoLayoutStrategy"]


def _sanitize_filename_fragment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned or "segment"


class EnglishVideoLayoutStrategy(VideoLayoutStrategy):
    """Provide per-segment layout rules for English renders."""

    locale = "en"

    _SEGMENT_BACKGROUNDS: Dict[str, str] = {
        "name": "info.mp4",
        "party": "party.mp4",
        "constituency": "board.mp4",
        "age": "info.mp4",
        "education": "degree.mp4",
        "criminal_cases": "cases.mp4",
        "assets": "assets.mp4",
        "liabilities": "assets.mp4",
    }

    _EDUCATION_BACKGROUNDS: Tuple[Tuple[str, str], ...] = (
        ("doctorate", "doctorate.mp4"),
        ("post graduate", "degree.mp4"),
        ("graduate", "degree.mp4"),
        ("professional", "degree.mp4"),
        ("literate", "literate.mp4"),
    )

    def __init__(
        self,
        *,
        background_directory: Path | None = None,
        output_directory: Path | None = None,
        primary_font: str | None = None,
    ) -> None:
        self._background_directory = (
            background_directory or Path("tests/video_pipeline/blue")
        ).resolve()
        self._output_directory = (
            output_directory
            or self._background_directory.parent / "output"
        ).resolve()
        self._output_directory.mkdir(parents=True, exist_ok=True)
        self._primary_font = primary_font

    @property
    def background_directory(self) -> Path:
        return self._background_directory

    @property
    def output_directory(self) -> Path:
        return self._output_directory

    def preferred_resolution(self) -> Tuple[int, int]:
        return (1080, 1920)

    def preferred_fps(self) -> int:
        return 30

    def background_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Path:
        filename = self._resolve_background_filename(segment)
        return (self._background_directory / filename).resolve()

    def text_layers_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Sequence[TextLayerSpec]:
        overlay = segment.overlay_text
        if overlay is None:
            return []

        text_value = (overlay.text or "").strip()
        if not text_value:
            return []

        return [
            TextLayerSpec(
                text=overlay.text,
                anchor=(0.5, 0.5),
                font=self._primary_font,
                font_size=100,
                max_width_ratio=0.9,
                box_color=None,
                box_opacity=0.0,
                color="#FFFFFF",
            )
        ]

    def output_filename_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> str:
        candidate_fragment = _sanitize_filename_fragment(
            assets.record.candidate_name
        )
        segment_fragment = _sanitize_filename_fragment(segment.key)
        return f"{candidate_fragment}_{segment_fragment}.mp4"

    def _resolve_background_filename(self, segment: SegmentAsset) -> str:
        if segment.key == "education" and segment.overlay_text is not None:
            text_value = (segment.overlay_text.text or "").strip().lower()
            primary = text_value.splitlines()[0] if text_value else ""
            for token, filename in self._EDUCATION_BACKGROUNDS:
                if token in primary:
                    return filename
        return self._SEGMENT_BACKGROUNDS.get(segment.key, "info.mp4")
