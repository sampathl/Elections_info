"""English locale layout strategy for video segments."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence, Tuple

from src.entities.narration_assets import CandidateNarrationAssets, SegmentAsset

from .base import ImageLayerSpec, TextLayerSpec, VideoLayoutStrategy
from ..paths import VIDEO_LOCALE_PATHS
from ..utils import sanitize_filename_fragment

__all__ = ["EnglishVideoLayoutStrategy"]


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
        party_symbol_path: Path | None = None,
    ) -> None:
        config = VIDEO_LOCALE_PATHS[self.locale]

        self._background_directory = (
            background_directory or config.background_directory
        ).resolve()
        self._output_directory = (
            output_directory or config.output_directory
        ).resolve()
        self._output_directory.mkdir(parents=True, exist_ok=True)
        self._primary_font = primary_font
        if party_symbol_path is not None:
            self._party_symbol_path = party_symbol_path.resolve()
        else:
            self._party_symbol_path = config.party_symbol_path

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

    def image_layers_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Sequence[ImageLayerSpec]:
        if segment.key != "party":
            return []
        if self._party_symbol_path is None or not self._party_symbol_path.exists():
            return []
        return [
            ImageLayerSpec(
                path=self._party_symbol_path,
                anchor=(0.5, 0.82),
                max_width_ratio=0.33,
                max_height_ratio=0.22,
                padding=(0, -40),
            )
        ]

    def output_filename_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> str:
        candidate_fragment = sanitize_filename_fragment(assets.record.candidate_name)
        segment_fragment = sanitize_filename_fragment(segment.key)
        return f"{candidate_fragment}_{segment_fragment}.mp4"

    def _resolve_background_filename(self, segment: SegmentAsset) -> str:
        if segment.key == "education" and segment.overlay_text is not None:
            text_value = (segment.overlay_text.text or "").strip().lower()
            primary = text_value.splitlines()[0] if text_value else ""
            for token, filename in self._EDUCATION_BACKGROUNDS:
                if token in primary:
                    return filename
        return self._SEGMENT_BACKGROUNDS.get(segment.key, "info.mp4")
