"""Utilities for stitching rendered segment clips into a single video."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .utils import write_videofile

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

    missing_paths = [path for path in video_paths if not Path(path).is_file()]
    if missing_paths:
        missing_list = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Cannot stitch videos; missing segment files: {missing_list}")

    clips = []
    final_clip = None

    try:
        for path in video_paths:
            try:
                clips.append(VideoFileClip(str(path)))
            except Exception as exc:
                raise RuntimeError(f"Failed to load segment clip '{path}': {exc}") from exc

        final_clip = concatenate_videoclips(clips, method="compose")
        write_videofile(final_clip, output_path, fps=fps)
    finally:
        if final_clip is not None:
            final_clip.close()
        for clip in clips:
            clip.close()

    return output_path
