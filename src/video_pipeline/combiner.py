"""Utilities for stitching rendered segment clips into a single video."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

try:  # Keep compatibility with either MoviePy namespace style.
    import moviepy as mp  # type: ignore

    VideoFileClip = mp.VideoFileClip  # type: ignore[attr-defined]
    concatenate_videoclips = mp.concatenate_videoclips  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback for legacy MoviePy installs.
    from moviepy.editor import VideoFileClip, concatenate_videoclips  # type: ignore


def stitch_videos(
    video_paths: Sequence[Path],
    output_path: Path,
    *,
    fps: int,
) -> Path:
    """Concatenate the provided video clips and persist the stitched output."""

    if not video_paths:
        raise ValueError("Cannot stitch videos; no segment clips were provided.")

    clips = []
    final_clip = None

    try:
        for path in video_paths:
            clips.append(VideoFileClip(str(path)))

        final_clip = concatenate_videoclips(clips, method="compose")
        _write_videofile(final_clip, output_path, fps=fps)
    finally:
        if final_clip is not None:
            final_clip.close()
        for clip in clips:
            clip.close()

    return output_path


def _write_videofile(clip, output_path: Path, *, fps: int) -> None:
    try:
        clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
        )
    except TypeError:  # pragma: no cover - legacy API option names.
        clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(output_path.with_suffix(".temp-audio.m4a")),
            remove_temp=True,
        )
