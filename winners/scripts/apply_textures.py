"""Blend light textures onto existing videos with MoviePy overlays."""

from __future__ import annotations

import logging
from pathlib import Path

from moviepy import CompositeVideoClip, ImageClip, VideoFileClip

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = PROJECT_ROOT / "tests" / "video_pipeline" / "output"
TEXTURE_DIR = PROJECT_ROOT / "tests" / "video_pipeline" / "texture"
OUTPUT_DIR = VIDEO_DIR / "textured"

# Lower value keeps the texture gentle; tweak if you need more or less presence.
TEXTURE_OPACITY = 0.12


def apply_textures_to_videos() -> None:
    """Create subtle textured variants for every video/texture combination."""
    if not VIDEO_DIR.exists():
        raise FileNotFoundError(f"Video directory not found: {VIDEO_DIR}")
    if not TEXTURE_DIR.exists():
        raise FileNotFoundError(f"Texture directory not found: {TEXTURE_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = sorted(VIDEO_DIR.glob("*.mp4"))
    textures = sorted(TEXTURE_DIR.glob("*.jpg"))

    if not videos:
        logging.warning("No videos found in %s", VIDEO_DIR)
        return
    if not textures:
        logging.warning("No textures found in %s", TEXTURE_DIR)
        return

    for video_path in videos:
        with VideoFileClip(str(video_path)) as clip:
            for texture_path in textures:
                output_path = OUTPUT_DIR / f"{video_path.stem}_{texture_path.stem}.mp4"
                logging.info("Rendering %s", output_path.name)

                texture_clip = (
                    ImageClip(str(texture_path))
                    .resized(clip.size)
                    .with_duration(clip.duration)
                    .with_opacity(TEXTURE_OPACITY)
                )

                composite = CompositeVideoClip([clip, texture_clip], size=clip.size)
                if clip.audio is not None:
                    composite = composite.with_audio(clip.audio)

                composite.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    preset="slow",
                    bitrate="3M",
                    fps=clip.fps or 30,
                )

                texture_clip.close()
                composite.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    apply_textures_to_videos()
