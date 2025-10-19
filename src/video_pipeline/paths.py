"""Shared filesystem helpers for video rendering assets."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from src.entities.candidate_record import CandidateRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = (PROJECT_ROOT / "output").resolve()
BACKGROUND_SET_ROOT = (
    PROJECT_ROOT / "static" / "background" / "back_ground_images" / "2025"
).resolve()


@dataclass(frozen=True)
class LocaleAssetConfig:
    """Immutable container for locale-specific static assets."""

    background_directory: Path
    party_symbol_path: Optional[Path] = None


LOCALE_ASSET_DIRECTORIES: dict[str, LocaleAssetConfig] = {
    "en": LocaleAssetConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "blue").resolve(),
        party_symbol_path=(
            PROJECT_ROOT
            / "static"
            / "Bihar"
            / "party_symbols"
            / "Communist_Party_of_India_(Marxist-Leninist)_Liberation.png"
        ).resolve(),
    ),
    "hi": LocaleAssetConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "brown").resolve(),
        party_symbol_path=(
            PROJECT_ROOT
            / "static"
            / "Bihar"
            / "party_symbols"
            / "Communist_Party_of_India_(Marxist-Leninist)_Liberation.png"
        ).resolve(),
    ),
}


def locale_assets(locale: str) -> LocaleAssetConfig:
    """Return background and static overlays for the locale."""
    try:
        return LOCALE_ASSET_DIRECTORIES[locale]
    except KeyError as exc:
        raise ValueError(f"Unsupported locale '{locale}'") from exc


def candidate_base_directory(record: CandidateRecord) -> Path:
    """Return the per-candidate output root."""
    constituency_id = str(record.constituency_id).strip()
    candidate_id = str(record.candidate_id).strip()
    if not constituency_id:
        raise ValueError("CandidateRecord.constituency_id is required for output directories.")
    if not candidate_id:
        raise ValueError("CandidateRecord.candidate_id is required for output directories.")
    return (OUTPUT_ROOT / constituency_id / candidate_id).resolve()


TEXTURE_DIRECTORY = (PROJECT_ROOT / "static" / "background" / "textures").resolve()
DISCLAIMER_IMAGE = (PROJECT_ROOT / "static" / "background" / "disclaimer.png").resolve()
CREDITS_IMAGE = (PROJECT_ROOT / "static" / "background" / "credits.png").resolve()


def _available_background_sets() -> Sequence[Path]:
    if not BACKGROUND_SET_ROOT.exists():
        return ()
    return [
        path for path in BACKGROUND_SET_ROOT.iterdir() if path.is_dir()
    ]


def choose_background_directory(locale: str, *, seed: Optional[str] = None) -> Path:
    """Return a background directory for the candidate, falling back to defaults."""
    candidates = list(_available_background_sets())
    if candidates:
        rng = random.Random(seed)
        return rng.choice(candidates).resolve()
    return locale_assets(locale).background_directory

