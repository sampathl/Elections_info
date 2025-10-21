"""Utilities for stitching rendered segment clips into a single video."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Sequence

import moviepy as mp  # type: ignore

from .paths import (
    CREDITS_IMAGE,
    DISCLAIMER_IMAGE,
    TEXTURE_DIRECTORY,
    choose_background_music,
)
from .utils import write_videofile

CompositeVideoClip = mp.CompositeVideoClip  # type: ignore[attr-defined]
CompositeAudioClip = mp.CompositeAudioClip  # type: ignore[attr-defined]
ImageClip = mp.ImageClip  # type: ignore[attr-defined]
AudioFileClip = mp.AudioFileClip  # type: ignore[attr-defined]
VideoFileClip = mp.VideoFileClip  # type: ignore[attr-defined]
concatenate_videoclips = mp.concatenate_videoclips  # type: ignore[attr-defined]

TEXTURE_OPACITY = 0.12
_TEXTURE_SUFFIXES = {".jpg", ".jpeg", ".png"}


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
    audio_resources: list = []
    final_clip = None
    texture_clip = None
    composite_clip = None
    disclaimer_clip = None
    credits_clip = None

    try:
        for path in video_paths:
            try:
                clips.append(VideoFileClip(str(path)))
            except Exception as exc:
                raise RuntimeError(f"Failed to load segment clip '{path}': {exc}") from exc

        target_size = clips[0].size if clips else None

        disclaimer_clip = _build_static_clip(DISCLAIMER_IMAGE, target_size)
        if disclaimer_clip is not None:
            clips.insert(0, disclaimer_clip)

        credits_clip = _build_static_clip(CREDITS_IMAGE, target_size)
        if credits_clip is not None:
            clips.append(credits_clip)

        final_clip = concatenate_videoclips(clips, method="compose")
        texture_clip = _build_texture_overlay(final_clip)

        clip_to_write = final_clip
        if texture_clip is not None:
            composite_clip = CompositeVideoClip([final_clip, texture_clip], size=final_clip.size)
            clip_to_write = composite_clip

        try: 
            clip_to_write = _apply_background_music(clip_to_write)
        except Exception as e:
            print("unable to add bgm, skipping it")
            print(e)

        write_videofile(clip_to_write, output_path, fps=fps)
    except Exception as e:
        print(e)
        raise e
        

    return output_path


def _build_texture_overlay(final_clip):
    """Return a texture clip sized to the final clip, or None if unavailable."""
    duration = getattr(final_clip, "duration", None)
    size = getattr(final_clip, "size", None)

    if not duration or not size:
        return None
    if not TEXTURE_DIRECTORY.exists():
        return None

    textures = [
        path
        for path in TEXTURE_DIRECTORY.iterdir()
        if path.suffix.lower() in _TEXTURE_SUFFIXES and path.is_file()
    ]
    if not textures:
        return None

    texture_path = random.choice(textures)
    clip = ImageClip(str(texture_path))
    clip = _resize_clip(clip, size)
    clip = _set_duration(clip, duration)
    clip = _set_opacity(clip, TEXTURE_OPACITY)
    return clip


def _apply_background_music(clip):

    music_path = choose_background_music()
    print(music_path)
    bgm= AudioFileClip(music_path).with_volume_scaled(0.1).subclipped(0, clip.duration)
    final = clip.with_audio(
        bgm if clip.audio is None else   CompositeAudioClip( [clip.audio,bgm])
        )
    try:
        print(bgm.duration)
    except Exception:
        print(Exception)
    return final


def _resize_clip(clip, size):
    if hasattr(clip, "resize"):
        return clip.resize(newsize=size)
    if hasattr(clip, "resized"):
        return clip.resized(size)
    return clip


def _set_duration(clip, duration):
    if hasattr(clip, "set_duration"):
        return clip.set_duration(duration)
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip


def _set_opacity(clip, opacity):
    if hasattr(clip, "set_opacity"):
        return clip.set_opacity(opacity)
    if hasattr(clip, "with_opacity"):
        return clip.with_opacity(opacity)
    return clip


def _build_static_clip(image_path: Path, size):
    if not image_path.exists():
        return None
    clip = ImageClip(str(image_path), duration=1)
    if size is not None and tuple(clip.size) != tuple(size):
        clip = _resize_clip(clip, size)
    return clip
