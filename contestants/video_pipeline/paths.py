"""Shared filesystem helpers for video rendering assets."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from contestants.entities.candidate_record import CandidateRecord
from contestants.video_pipeline.utils import sanitize_filename_fragment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_WINNER_OUTPUT_BASE = PROJECT_ROOT / "static" / "Bihar" / "contestants"
_DEFAULT_YEAR = "2025"
OUTPUT_ROOT = (_WINNER_OUTPUT_BASE / _DEFAULT_YEAR).resolve()
BACKGROUND_SET_ROOT = (
    PROJECT_ROOT / "static" / "background" / "back_ground_images" / "2025"
).resolve()
CANDIDATE_IMAGE_ROOT = (
    PROJECT_ROOT / "static" / "Bihar" / "2025_data" / "candidate_static"
).resolve()

_PARTY_IMAGE_LOOKUP = {'bjp': 0,
 'cpi(ml)(l)': 2,
 'voters party international': 3,
 'jan suraaj party': 4,
 'bsp': 5,
 'janshakti janta dal': 6,
 'rashtriya jansambhavna party': 8,
 'vikassheel insaan party': 9,
 'jd(u)': 10,
 'rjd': 11,
 'rashtriya lok janshakti party': 12,
 'aap': 15,
 'the plurals party': 20,
 'aazad samaj party (kanshi ram)': 29,
 'cpi': 30,
 'inc': 31,
 'lok janshakti party (ram vilas)': 36,
 'right to recall party': 38,
 'samata party': 43,    
 'cpi(m)': 50,
 'suheldev bharatiya samaj party': 55,
 'all india majlis-e-ittehadul muslimeen': 61
 }

_PARTY_SYMBOL_EXTENSIONS: Sequence[str] = (".png", ".jpg", ".jpeg", ".svg")
_PARTY_SYMBOL_SOURCE_DIRS: Sequence[Path] = (
    PROJECT_ROOT / "staticBihar" / "party_symbols",
    PROJECT_ROOT / "static" / "Bihar" / "party_symbols",
    PROJECT_ROOT / "static" / "Bihar" / "party_symbols" / "image_id",
    PROJECT_ROOT / "static" / "Party" / "images",
)


def _existing_party_symbol_dirs() -> Sequence[Path]:
    """Return party symbol directories that exist on disk."""
    return [path.resolve() for path in _PARTY_SYMBOL_SOURCE_DIRS if path.exists()]


def configure_output_year(year: str) -> Path:
    """Set and return the output directory root for the provided election year."""
    global OUTPUT_ROOT
    selected_year = str(year).strip() or _DEFAULT_YEAR
    OUTPUT_ROOT = (_WINNER_OUTPUT_BASE / selected_year).resolve()
    return OUTPUT_ROOT


@dataclass(frozen=True)
class LocaleAssetConfig:
    """Immutable container for locale-specific static assets."""

    background_directory: Path
    party_symbol_path: Optional[Path] = None


LOCALE_ASSET_DIRECTORIES: dict[str, LocaleAssetConfig] = {
    "en": LocaleAssetConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "blue").resolve(),
        party_symbol_path=None,
    ),
    "hi": LocaleAssetConfig(
        background_directory=(PROJECT_ROOT / "tests" / "video_pipeline" / "brown").resolve(),
        party_symbol_path=None,
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
BACKGROUND_MUSIC_DIRECTORY = (
    PROJECT_ROOT / "static" / "Bihar" / "background_music"
).resolve()
_MUSIC_SUFFIXES = (".mp3", ".m4a", ".wav")


def _available_background_sets() -> Sequence[Path]:
    if not BACKGROUND_SET_ROOT.exists():
        return ()
    return [path for path in BACKGROUND_SET_ROOT.iterdir() if path.is_dir()]


def choose_background_directory(locale: str, *, seed: Optional[str] = None) -> Path:
    """Return a background directory for the candidate, falling back to defaults."""
    candidates = list(_available_background_sets())
    if candidates:
        rng = random.Random(seed)
        return rng.choice(candidates).resolve()
    return locale_assets(locale).background_directory


def choose_background_music(seed: Optional[str] = None) -> Optional[Path]:
    """Return a background music file if available."""
    if not BACKGROUND_MUSIC_DIRECTORY.exists():
        return None

    candidates = sorted(
        path
        for path in BACKGROUND_MUSIC_DIRECTORY.iterdir()
        if path.is_file() and path.suffix.lower() in _MUSIC_SUFFIXES
    )
    if not candidates:
        return None

    if seed is None:
        rng = random.Random()
        return rng.choice(candidates)

    rng = random.Random(seed)
    return rng.choice(candidates)


def resolve_party_symbol_path(party: str) -> Optional[Path]:
    """Return the best matching party symbol path for the provided party name."""
    normalized = (party or "").strip()
    if not normalized:
        return None

    lookup_key = normalized.lower()
    index = _PARTY_IMAGE_LOOKUP.get(lookup_key)

    base_candidates: list[str] = []
    if index is not None:
        base_candidates.append(str(index))

    sanitized = _sanitize_filename_fragment(normalized)
    if sanitized:
        base_candidates.extend({sanitized, sanitized.lower(), sanitized.upper()})

    existing_dirs = _existing_party_symbol_dirs()
    for base in base_candidates:
        for directory in existing_dirs:
            for extension in _PARTY_SYMBOL_EXTENSIONS:
                candidate = (directory / f"{base}{extension}").resolve()
                if candidate.exists():
                    return candidate
    return None


def resolve_candidate_image_path(candidate_id: str | int | None) -> Optional[Path]:
    """Return the candidate image path for the provided candidate id."""
    if candidate_id is None:
        return None

    identifier = str(candidate_id).strip()
    if not identifier:
        return None

    candidate_path = (CANDIDATE_IMAGE_ROOT / f"{identifier}.jpg").resolve()
    if candidate_path.exists():
        return candidate_path

    # Fallback: normalise numeric identifiers that may include leading zeros or decimals.
    normalized_numeric: Optional[str] = None
    try:
        # Attempt to interpret as float first to handle values like "19.0".
        numeric_value = float(identifier)
        if numeric_value.is_integer():
            normalized_numeric = str(int(numeric_value))
        else:
            normalized_numeric = None
    except ValueError:
        try:
            normalized_numeric = str(int(identifier))
        except ValueError:
            normalized_numeric = None

    if normalized_numeric and normalized_numeric != identifier:
        normalized_path = (CANDIDATE_IMAGE_ROOT / f"{normalized_numeric}.jpg").resolve()
        if normalized_path.exists():
            return normalized_path

    return None


def _sanitize_filename_fragment(value: str) -> str:
    """Return a filesystem-friendly fragment for attempting symbol lookups."""
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def combined_video_directory(record: CandidateRecord, locale: str) -> Path:
    """Return the directory for storing combined videos."""
    constituency_id = sanitize_filename_fragment(record.constituency_id or "unknown")
    locale_fragment = sanitize_filename_fragment(locale or "xx")
    combined_root = (_WINNER_OUTPUT_BASE / "Combined" / constituency_id / locale_fragment).resolve()
    combined_root.mkdir(parents=True, exist_ok=True)
    return combined_root


def combined_video_filename(record: CandidateRecord, locale: str, stitched_path: Path) -> str:
    """Return the filename for combined video copies."""
    candidate_fragment = sanitize_filename_fragment(record.candidate_id or "unknown")
    year_fragment = sanitize_filename_fragment(record.election_year or _DEFAULT_YEAR)
    return f"{candidate_fragment}_{year_fragment}{stitched_path.suffix}"
