"""Hindi locale layout strategy for video segments."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple

from src.entities.narration_assets import CandidateNarrationAssets, SegmentAsset

from .base import TextLayerSpec, VideoLayoutStrategy
from ..utils import sanitize_filename_fragment

__all__ = ["HindiVideoLayoutStrategy"]

DEVANAGARI_FONT_PATH = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"


class HindiVideoLayoutStrategy(VideoLayoutStrategy):
    """Provide per-segment layout rules for Hindi renders."""

    locale = "hi"

    _SEGMENT_BACKGROUNDS: Dict[str, str] = {
        "name": "info_hindi.mp4",
        "party": "party_hindi.mp4",
        "constituency": "board_hindi.mp4",
        "age": "info_hindi.mp4",
        "education": "degree_hindi.mp4",
        "criminal_cases": "cases_hindi.mp4",
        "assets": "assets_hindi.mp4",
        "liabilities": "assets_hindi.mp4",
    }

    _EDUCATION_BACKGROUNDS: Tuple[Tuple[str, str], ...] = (
        ("डॉक्टरेट", "doctorate_hindi.mp4"),
        ("doctorate", "doctorate_hindi.mp4"),
        ("स्नातकोत्तर", "degree_hindi.mp4"),
        ("post graduate", "degree_hindi.mp4"),
        ("स्नातक", "degree_hindi.mp4"),
        ("graduate", "degree_hindi.mp4"),
        ("व्यावसायिक", "degree_hindi.mp4"),
        ("professional", "degree_hindi.mp4"),
        ("साक्षर", "literate_hindi.mp4"),
        ("literate", "literate_hindi.mp4"),
    )

    def __init__(
        self,
        *,
        background_directory: Path | None = None,
        output_directory: Path | None = None,
        primary_font: str | None = None,
    ) -> None:
        self._background_directory = (
            background_directory or Path("tests/video_pipeline/brown")
        ).resolve()
        self._output_directory = (
            output_directory or self._background_directory.parent / "output"
        ).resolve()
        self._output_directory.mkdir(parents=True, exist_ok=True)
        self._primary_font = primary_font or DEVANAGARI_FONT_PATH

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
                font_size=120,
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
        candidate_fragment = sanitize_filename_fragment(
            assets.record.candidate_name, allow_unicode=True
        )
        segment_fragment = sanitize_filename_fragment(
            segment.key, allow_unicode=True
        )
        return f"{candidate_fragment}_{segment_fragment}_hi.mp4"

    def _resolve_background_filename(self, segment: SegmentAsset) -> str:
        if segment.key == "education" and segment.overlay_text is not None:
            text_value = (segment.overlay_text.text or "").strip().lower()
            primary = text_value.splitlines()[0] if text_value else ""
            for token, filename in self._EDUCATION_BACKGROUNDS:
                if token in primary:
                    return filename
        return self._SEGMENT_BACKGROUNDS.get(segment.key, "info_hindi.mp4")
