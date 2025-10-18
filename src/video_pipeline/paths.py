"""Shared filesystem locations for video rendering assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LocalePathConfig:
    """Container for locale-specific asset directories."""

    background_directory: Path
    output_directory: Path
    party_symbol_path: Optional[Path] = None


VIDEO_OUTPUT_DIRECTORY = (PROJECT_ROOT / "tests" / "video_pipeline" / "output").resolve()

VIDEO_LOCALE_PATHS: dict[str, LocalePathConfig] = {
    "en": LocalePathConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "blue").resolve(),
        output_directory=VIDEO_OUTPUT_DIRECTORY,
        party_symbol_path=(
            PROJECT_ROOT
            / "static"
            / "Bihar"
            / "party_symbols"
            / "Communist_Party_of_India_(Marxist-Leninist)_Liberation.png"
        ).resolve(),
    ),
    "hi": LocalePathConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "brown").resolve(),
        output_directory=VIDEO_OUTPUT_DIRECTORY,
        party_symbol_path=(
            PROJECT_ROOT
            / "static"
            / "Bihar"
            / "party_symbols"
            / "Communist_Party_of_India_(Marxist-Leninist)_Liberation.png"
        ).resolve(),
    ),
}

TEXTURE_DIRECTORY = (
    PROJECT_ROOT / "static" / "background" / "textures"
).resolve()

AUDIO_OUTPUT_DIRECTORY = (PROJECT_ROOT / "tests" / "audio").resolve()
