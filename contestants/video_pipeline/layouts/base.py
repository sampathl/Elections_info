"""Shared data structures and interfaces for video layouts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, Tuple

from winners.entities.narration_assets import CandidateNarrationAssets, SegmentAsset


@dataclass(frozen=True)
class TextLayerSpec:
    """Describe a block of text to render on top of a video clip."""

    text: str
    anchor: Tuple[float, float] = (0.5, 0.78)
    max_width_ratio: float = 0.8
    font: str | None = None
    font_size: int = 100
    color: str = "#FFFFFF"
    align: str = "center"
    line_spacing: int | None = None
    box_color: str | None = "#000000"
    box_opacity: float = 0.00
    padding: int = 0
    shadow_color: str | None = "#000000"
    shadow_offset: Tuple[int, int] = (3, 3)


@dataclass(frozen=True)
class ImageLayerSpec:
    """Describe an image overlay to render on top of a video clip."""

    path: Path
    anchor: Tuple[float, float] = (0.5, 0.85)
    max_width_ratio: float = 0.5
    max_height_ratio: float = 0.33
    padding: Tuple[int, int] = (0, 0)


class VideoLayoutStrategy(Protocol):
    """Protocol for locale-specific video layout strategies."""

    locale: str

    @property
    def background_directory(self) -> Path:
        ...

    @property
    def output_directory(self) -> Path:
        ...

    def background_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Path:
        """Return the background clip path for the provided segment."""

    def text_layers_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Sequence[TextLayerSpec]:
        """Return the ordered text layers that should be rendered."""

    def image_layers_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Sequence[ImageLayerSpec]:
        """Return the ordered image layers that should be rendered."""

    def output_filename_for_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> str:
        """Return the file name to use for the rendered video."""

    def preferred_resolution(self) -> Tuple[int, int]:
        """Return the (width, height) resolution for the final render."""

    def preferred_fps(self) -> int:
        """Return the desired frames per second for the render."""
