"""Manifest generation utilities for YouTube uploads."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Sequence

from . import config
from .logging_utils import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class ManifestRow:
    """Represents a single row in a video upload manifest."""
    video_id: str
    video_name: str
    video_location: str
    playlist_id: str


def normalize_extensions(extensions: Sequence[str]) -> List[str]:
    """Normalise a collection of file extensions for comparison."""
    normalised: List[str] = []
    for ext in extensions:
        if not ext:
            continue
        cleaned = ext.strip().lower()
        if not cleaned:
            continue
        if not cleaned.startswith("."):
            cleaned = f".{cleaned}"
        normalised.append(cleaned)
    if not normalised:
        raise ValueError("At least one file extension must be provided")
    return normalised


def iter_video_files(
    directory: Path,
    extensions: Sequence[str],
    recursive: bool = False,
) -> Iterator[Path]:
    """Yield video file paths in the provided directory."""
    directory = directory.expanduser().resolve()
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Expected directory: {directory}")

    allowed_exts = set(normalize_extensions(extensions))
    walker = directory.rglob("*") if recursive else directory.glob("*")
    matched = sorted(
        path
        for path in walker
        if path.is_file() and path.suffix.lower() in allowed_exts
    )
    for path in matched:
        yield path


def build_manifest_rows(
    videos: Sequence[Path],
    playlist_id: str,
) -> List[ManifestRow]:
    """Convert video paths into manifest rows."""
    if not playlist_id.strip():
        raise ValueError("Playlist ID must be a non-empty string")
    rows: List[ManifestRow] = []
    for video in videos:
        if not video.exists() or not video.is_file():
            raise FileNotFoundError(f"Video file missing: {video}")
        video_id = video.stem
        rows.append(
            ManifestRow(
                video_id=video_id,
                video_name=video_id,
                video_location=str(video),
                playlist_id=playlist_id,
            )
        )
    return rows


def write_manifest(output_path: Path, rows: Sequence[ManifestRow]) -> None:
    """Write manifest rows to a CSV file."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            ["video_id", "video_name", "video_location", "playlist_id"]
        )
        for row in rows:
            writer.writerow(
                [row.video_id, row.video_name, row.video_location, row.playlist_id]
            )
    _logger.info("Wrote manifest with %s rows to %s", len(rows), output_path)


def create_manifest_from_directory(
    directory: str,
    output: str | None = None,
    playlist_id: str = config.DEFAULT_PLAYLIST_ID,
    extensions: Sequence[str] = config.VIDEO_EXTENSIONS,
    recursive: bool = False,
) -> Path:
    """Discover video files and write a manifest CSV."""
    source_dir = Path(directory)
    video_files = list(
        iter_video_files(source_dir, extensions=extensions, recursive=recursive)
    )
    if not video_files:
        raise RuntimeError(
            f"No video files found in {source_dir} for extensions {extensions}"
        )

    rows = build_manifest_rows(video_files, playlist_id=playlist_id)
    output_path = Path(output).expanduser() if output else config.DEFAULT_MANIFEST_PATH
    write_manifest(output_path, rows)
    return output_path.resolve()
