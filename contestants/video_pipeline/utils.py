"""Shared helpers for video pipeline components."""

from __future__ import annotations

import re
from pathlib import Path


def sanitize_filename_fragment(
    value: str,
    *,
    allow_unicode: bool = False,
    default: str = "segment",
) -> str:
    """Return a filesystem-friendly fragment derived from the provided text."""
    if allow_unicode:
        cleaned = "".join(ch if ch.isalnum() else "_" for ch in value)
    else:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    cleaned = cleaned.strip("_")
    return cleaned or default


def write_videofile(clip, output_path: Path, *, fps: int) -> None:
    """Persist a MoviePy clip to disk using consistent encoder defaults."""
    try:
        clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
        )
    except TypeError:
        clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(output_path.with_suffix(".temp-audio.m4a")),
            remove_temp=True,
        )
