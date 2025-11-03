"""Rendering utilities for per-segment video generation."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Tuple, Union

try:  # Prefer the newer MoviePy API when available.
    import moviepy as mp  # type: ignore

    AudioFileClip = mp.AudioFileClip  # type: ignore[attr-defined]
    CompositeVideoClip = mp.CompositeVideoClip  # type: ignore[attr-defined]
    ImageClip = mp.ImageClip  # type: ignore[attr-defined]
    TextClip = mp.TextClip  # type: ignore[attr-defined]
    VideoFileClip = mp.VideoFileClip  # type: ignore[attr-defined]
    if hasattr(mp, "vfx"):  # type: ignore[attr-defined]
        vfx = mp.vfx  # type: ignore[attr-defined]
    else:  # pragma: no cover - compatibility fallback
        import moviepy.video.fx.all as vfx  # type: ignore
    concatenate_videoclips = mp.concatenate_videoclips  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback to legacy API
    from moviepy.editor import (  # type: ignore
        AudioFileClip,
        CompositeVideoClip,
        ImageClip,
        concatenate_videoclips,
        TextClip,
        VideoFileClip,
    )
    import moviepy.video.fx.all as vfx  # type: ignore

from contestants.entities.narration_assets import CandidateNarrationAssets, SegmentAsset

from .layouts.base import ImageLayerSpec, TextLayerSpec, VideoLayoutStrategy
from .tests.size_helper import load_font, wrap_text_no_breaks
from .utils import write_videofile
from contestants.utils.logging_config import PipelineLoggerAdapter, get_pipeline_logger


@dataclass(frozen=True)
class RenderResult:
    segment_key: str
    output_path: Path


class SegmentVideoRenderer:
    """Compose background, text layers, and audio into a segment video clip."""

    def __init__(
        self,
        *,
        layout_strategy: VideoLayoutStrategy,
        logger: Union[PipelineLoggerAdapter, logging.Logger, None] = None,
    ) -> None:
        self._layout = layout_strategy
        self._resolution = self._layout.preferred_resolution()
        self._fps = self._layout.preferred_fps()
        if logger is None:
            base_logger = get_pipeline_logger(__name__, component="segment_renderer")
        elif isinstance(logger, PipelineLoggerAdapter):
            base_logger = logger.bind(component="segment_renderer")
        else:
            base_logger = PipelineLoggerAdapter(logger, {"component": "segment_renderer"})
        self._logger = base_logger.bind(segment="-")

    def render_segments(
        self,
        assets: CandidateNarrationAssets,
        segments: Iterable[SegmentAsset],
    ) -> Sequence[RenderResult]:
        segment_list = list(segments)
        batch_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            segment="-",
        )
        batch_logger.debug("Rendering %d segment(s)", len(segment_list))
        results: list[RenderResult] = []
        for segment in segment_list:
            try:
                output_path = self.render_segment(assets, segment)
            except Exception:
                batch_logger.bind(segment=segment.key).exception("Segment render failed")
                raise
            if output_path is not None:
                results.append(RenderResult(segment_key=segment.key, output_path=output_path))
        return results

    def render_segment(
        self,
        assets: CandidateNarrationAssets,
        segment: SegmentAsset,
    ) -> Path | None:
        segment_logger = self._logger.bind(
            candidate=assets.record.candidate_id or assets.record.candidate_name or "-",
            segment=segment.key,
        )
        if segment.audio_path is None:
            # Cannot render without audio to set the duration.
            segment_logger.warning("Skipping render; audio missing for segment")
            return None
        if segment.overlay_text is None:
            # Defer rendering until overlay text has been populated.
            segment_logger.warning("Skipping render; overlay text missing for segment")
            return None

        background_path = self._layout.background_for_segment(assets, segment)
        text_layers = self._layout.text_layers_for_segment(assets, segment)
        if not any(layer.text.strip() for layer in text_layers):
            segment_logger.warning("Skipping render; overlay text empty for segment")
            return None

        image_layers = self._layout.image_layers_for_segment(assets, segment)
        if image_layers:
            segment_logger.debug(
                "Resolved %d image layer(s): %s",
                len(image_layers),
                [str(layer.path) for layer in image_layers],
            )
        else:
            segment_logger.debug("No image layers resolved for segment")
        if segment.key == "party" and not image_layers:
            segment_logger.warning("Skipping render; no party symbol available for segment")
            #return None

        duration = self._determine_duration(segment)
        segment_logger.debug("Segment duration determined as %.2fs", duration)
        output_path = self._layout.output_directory / self._layout.output_filename_for_segment(
            assets, segment
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._compose_clip(
                background_path=background_path,
                text_layers=text_layers,
                image_layers=image_layers,
                audio_path=segment.audio_path,
                duration=duration,
                output_path=output_path,
            )
        except Exception:
            segment_logger.exception("Failed to compose video clip")
            raise

        assets.update_segment(segment.key, video_path=output_path)
        segment_logger.info("Rendered segment clip at %s", output_path)
        return output_path

    def _determine_duration(self, segment: SegmentAsset) -> float:
        with AudioFileClip(str(segment.audio_path)) as audio_clip:
            audio_duration = audio_clip.duration
        return audio_duration

    def _compose_clip(
        self,
        *,
        background_path: Path,
        text_layers: Sequence[TextLayerSpec],
        image_layers: Sequence[ImageLayerSpec],
        audio_path: Path,
        duration: float,
        output_path: Path,
    ) -> None:
        base_clip = None
        audio_clip = None
        overlay_clips: list = []
        composite = None

        try:
            base_clip = VideoFileClip(str(background_path))
            clip_duration = getattr(base_clip, "duration", None) or 0.0
            margin = 0.3

            if clip_duration + margin < duration:
                base_clip = self._loop_clip(base_clip, duration)
            else:
                trimmed_duration = min(duration, max(0, clip_duration))
                if trimmed_duration <= 0:
                    raise RuntimeError(
                        f"Background clip '{background_path}' has non-positive duration."
                    )
                adjusted_end = min(trimmed_duration, clip_duration)
                base_clip = self._subclip(base_clip, 0, adjusted_end)

            if tuple(base_clip.size) != tuple(self._resolution):
                base_clip = self._resize(base_clip, self._resolution)
            base_clip = self._with_duration(base_clip, duration)

            for layer in text_layers:
                clip = self._create_text_clip(layer, duration)
                overlay_clips.append(clip)

            for layer in image_layers:
                clip = self._create_image_clip(layer, duration)
                overlay_clips.append(clip)

            composite = CompositeVideoClip(
                [base_clip] + overlay_clips,
                size=self._resolution,
            )
            composite = self._with_duration(composite, duration)

            audio_clip = AudioFileClip(str(audio_path))
            audio_clip = self._with_duration(audio_clip, duration)
            composite = self._with_audio(composite, audio_clip)

            write_videofile(composite, output_path, fps=self._fps)
        finally:
            if composite is not None:
                composite.close()
            if base_clip is not None:
                base_clip.close()
            if audio_clip is not None:
                audio_clip.close()
            for clip in overlay_clips:
                clip.close()

    def _create_text_clip(
        self,
        spec: TextLayerSpec,
        duration: float,
    ):
        max_text_width = max(1, int(self._resolution[0] * spec.max_width_ratio))

        text_clip = self._build_text_clip(
            text=spec.text,
            font=spec.font,
            font_size=spec.font_size,
            color=spec.color,
            align=spec.align,
            max_width=max_text_width,
            interline=spec.line_spacing,
        )
        text_clip = self._with_duration(text_clip, duration)

        width, height = self._resolution
        anchor_x, anchor_y = spec.anchor
        text_w, text_h = text_clip.size

        # Convert the desired top padding into a ratio of the video height so positioning stays relative.
        if spec.padding is None:
            padding_ratio = 20 / height
        else:
            padding_value = max(0, spec.padding)
            padding_ratio = padding_value / height

        position_x = max(0, min(width - text_w, anchor_x * width - text_w / 2))
        position_y = anchor_y * height - text_h / 2 + padding_ratio * height
        position_y = max(0, min(height - text_h, position_y))
        text_clip = self._with_position(text_clip, (position_x, position_y))
        return text_clip

    def _build_text_clip(
        self,
        *,
        text: str,
        font: str | None,
        font_size: int,
        color: str | None,
        align: str,
        max_width: int,
        interline: int | None,
    ):
        text_value = self._double_spaced(text or "")
        font_path = self._resolve_font(font)

        wrapped_font = None
        if font_path:
            try:
                wrapped_font = load_font(font_path, font_size)
            except Exception:
                wrapped_font = None

        if wrapped_font is not None and max_width > 0:
            layout = wrap_text_no_breaks(
                text_value,
                wrapped_font,
                max_width_px=max_width,
                line_spacing_ratio=(interline / font_size) if interline else 0.25,
            )
            text_value = "\n\n".join(layout["lines"])

        kwargs = {
            "text": text_value,
            "font_size": font_size,
            "color": color or "#FFFFFF",
            "text_align": align,
            #"vertical_align": "top",
            "stroke_width" : 1.5, 
            "method": "caption",
            "size": (max_width, self._resolution[1]),
        }

        if font_path:
            kwargs["font"] = font_path
        if interline is not None and interline > 0:
            kwargs["interline"] = interline

        try:
            return TextClip(**kwargs)
        except TypeError:
            kwargs.pop("interline", None)
            fallback_kwargs = {
                "text": "\n" +text_value+ "\n ",
                "fontsize": font_size,
                "color": color or "#FFFFFF",
                "align": align,
                "method": "label",
            }
            if font_path:
                fallback_kwargs["font"] = font_path
            return TextClip(**fallback_kwargs)

    def _create_image_clip(
        self,
        spec: ImageLayerSpec,
        duration: float,
    ):
        try:
            image_clip = ImageClip(str(spec.path))
        except Exception as exc:
            raise RuntimeError(f"Failed to load image overlay '{spec.path}': {exc}") from exc

        width, height = self._resolution
        max_width = max(1, int(width * spec.max_width_ratio))
        max_height = max(1, int(height * spec.max_height_ratio))

        clip_w, clip_h = image_clip.size
        if clip_w == 0 or clip_h == 0:
            raise RuntimeError(f"Image overlay '{spec.path}' has invalid dimensions.")

        scale_factor = min(
            1.0,
            max_width / clip_w,
            max_height / clip_h,
        )

        if scale_factor < 1.0:
            target_size = (
                max(1, int(clip_w * scale_factor)),
                max(1, int(clip_h * scale_factor)),
            )
            image_clip = self._resize(image_clip, target_size)

        image_clip = self._with_duration(image_clip, duration)

        anchor_x, anchor_y = spec.anchor
        img_w, img_h = image_clip.size
        padding_x, padding_y = spec.padding

        position_x = anchor_x * width - img_w / 2 + padding_x
        position_y = anchor_y * height - img_h / 2 + padding_y

        position_x = max(0, min(width - img_w, position_x))
        position_y = max(0, min(height - img_h, position_y))

        image_clip = self._with_position(image_clip, (position_x, position_y))
        return image_clip

    @staticmethod
    def _resolve_font(font: str | None) -> str | None:
        if not font:
            return None
        path = Path(font)
        if path.exists():
            return str(path)
        return font

    @staticmethod
    def _with_duration(clip, duration: float):
        setter = getattr(clip, "with_duration", None)
        if callable(setter):
            return setter(duration)
        return clip.set_duration(duration)

    @staticmethod
    def _with_position(clip, position: tuple[float, float]):
        setter = getattr(clip, "with_position", None)
        if callable(setter):
            return setter(position)
        return clip.set_position(position)

    @staticmethod
    def _with_audio(clip, audio_clip):
        setter = getattr(clip, "with_audio", None)
        if callable(setter):
            return setter(audio_clip)
        return clip.set_audio(audio_clip)

    @staticmethod
    def _loop_clip(clip, duration: float):
        loop_fn = getattr(clip, "loop", None)
        if callable(loop_fn):
            return loop_fn(duration=duration)
        loop_effect = getattr(vfx, "loop", None)
        if callable(loop_effect):
            return clip.fx(loop_effect, duration=duration)
        clip_duration = getattr(clip, "duration", None)
        if not clip_duration or clip_duration <= 0:
            raise RuntimeError("Background clip has non-positive duration; cannot extend.")
        repeats = max(1, int(math.ceil(duration / clip_duration)))
        clips = [clip] + [clip.copy() for _ in range(repeats - 1)]
        extended = concatenate_videoclips(clips, method="compose")
        if getattr(extended, "duration", 0) > duration:
            extended = SegmentVideoRenderer._subclip(extended, 0, duration)
        return extended

    @staticmethod
    def _subclip(clip, start: float, end: float):
        setter = getattr(clip, "subclipped", None)
        if callable(setter):
            return setter(start, end)
        return clip.subclip(start, end)

    @staticmethod
    def _resize(clip, size: Tuple[int, int]):
        setter = getattr(clip, "resized", None)
        if callable(setter):
            return setter(size)
        return clip.resize(newsize=size)

    @staticmethod
    def _double_spaced(text: str) -> str:
        lines = text.splitlines()
        if not lines:
            return text
        return "\n\n".join(lines)
