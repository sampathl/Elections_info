"""Helpers for managing YouTube playlists."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import config
from .logging_utils import get_logger

_logger = get_logger(__name__)


def add_video_to_playlist(
    service: Any,
    playlist_id: str,
    video_id: str,
    position: Optional[int] = None,
) -> str:
    """Insert a video into a playlist and return the playlist item ID."""
    if not playlist_id.strip():
        raise ValueError("Playlist ID must be provided")
    if not video_id.strip():
        raise ValueError("Video ID must be provided")

    body: Dict[str, Any] = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    if position is not None:
        body["snippet"]["position"] = position

    response = (
        service.playlistItems()
        .insert(part="snippet", body=body)
        .execute()
    )
    playlist_item_id = response.get("id")
    if not playlist_item_id:
        raise RuntimeError("Playlist insertion response missing ID")
    _logger.info(
        "Inserted video %s into playlist %s (playlist_item_id=%s)",
        video_id,
        playlist_id,
        playlist_item_id,
    )
    return str(playlist_item_id)


def create_playlists(
    service: Any,
    titles: Sequence[str],
    descriptions: Optional[Sequence[str]] = None,
    *,
    privacy: str = config.DEFAULT_PRIVACY_STATUS,
    default_description: str = "",
    language: str = "en",
) -> List[Dict[str, str]]:
    """Create YouTube playlists and return metadata for each."""
    if descriptions and len(descriptions) != len(titles):
        raise ValueError("Descriptions length must match titles length")

    results: List[Dict[str, str]] = []
    for index, title in enumerate(titles):
        if not title.strip():
            raise ValueError("Playlist title cannot be blank")
        description = (
            descriptions[index] if descriptions else default_description
        ) or ""
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "defaultLanguage": language,
            },
            "status": {"privacyStatus": privacy},
        }
        response = (
            service.playlists()
            .insert(part="snippet,status", body=body)
            .execute()
        )
        playlist_id = response.get("id")
        if not playlist_id:
            raise RuntimeError("Playlist creation response missing ID")
        result = {"id": str(playlist_id), "title": title}
        results.append(result)
        _logger.info(
            "Created playlist %s with ID %s", title, playlist_id
        )
    return results


def parse_constituency_file(
    file_path: str,
    start_from: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Parse a constituency file into playlist titles and descriptions."""
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Constituency file not found: {path}")

    titles: List[str] = []
    descriptions: List[str] = []
    started = start_from is None

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if " - " in line:
                name, url = [part.strip() for part in line.split(" - ", 1)]
            else:
                name, url = line, ""
            if not started:
                if name == start_from:
                    started = True
                else:
                    continue
            playlist_title = name
            description = f"{name} Constituency"
            if url:
                description = f"{description}\nMore information: {url}"
            titles.append(playlist_title)
            descriptions.append(description)

    if not titles:
        raise RuntimeError(
            f"No entries parsed from constituency file {path}"
        )

    _logger.info(
        "Parsed %s entries from constituency file %s", len(titles), path
    )
    return titles, descriptions


def save_results_to_file(
    results: Sequence[Dict[str, str]],
    output_path: str,
) -> None:
    """Persist playlist creation results to disk as JSON."""
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(list(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _logger.info("Saved playlist results to %s", path)
