"""List videos in the configured YouTube channel with simple filtering options."""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

try:
    from . import config
    from .client import get_youtube_service
    from .logging_utils import get_logger
except ImportError:  # pragma: no cover - allow running as a script
    import sys as _sys
    from pathlib import Path as _Path

    _PACKAGE_ROOT = _Path(__file__).resolve().parents[1]
    _sys.path.append(str(_PACKAGE_ROOT.parent))

    from social_media_connectors.youtube import config
    from social_media_connectors.youtube.client import get_youtube_service
    from social_media_connectors.youtube.logging_utils import get_logger

_logger = get_logger(__name__)

YOUTUBE_VIDEO_BASE_URL = "https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class VideoRecord:
    video_id: str
    title: str
    visibility: str
    duration: str
    file_size_bytes: Optional[int]

    @property
    def video_url(self) -> str:
        return YOUTUBE_VIDEO_BASE_URL.format(video_id=self.video_id)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List videos in the configured YouTube channel.",
    )
    parser.add_argument(
        "--client-secrets-file",
        type=Path,
        default=Path(config.DEFAULT_CLIENT_SECRETS_FILE),
        help="Path to the OAuth client secrets file.",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(config.DEFAULT_TOKEN_FILE),
        help="Path to the OAuth token file.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum number of videos to fetch per API page (1-50).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of videos to output.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    parser.add_argument(
        "--channel-id",
        help="Optional explicit channel ID (defaults to authenticated user's channel).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        help="Optional path to write matching videos to a CSV file.",
    )
    return parser.parse_args(argv)


def fetch_channel_videos(
    service: Any,
    *,
    channel_id: Optional[str],
    max_results: int,
    limit: Optional[int],
) -> List[VideoRecord]:
    uploads_playlist_id = _resolve_uploads_playlist_id(service, channel_id)
    if not uploads_playlist_id:
        _logger.warning("Unable to determine uploads playlist for the channel.")
        return []

    videos: List[VideoRecord] = []
    next_page_token: Optional[str] = None

    while True:
        playlist_request = service.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results,
            pageToken=next_page_token,
        )
        playlist_response = playlist_request.execute()
        items = playlist_response.get("items", [])
        video_ids = [
            item.get("contentDetails", {}).get("videoId")
            for item in items
        ]
        video_ids = [vid for vid in video_ids if vid]

        if not video_ids:
            break

        details_request = service.videos().list(
            part="snippet,contentDetails,status,statistics,fileDetails",
            id=",".join(video_ids),
            maxResults=len(video_ids),
        )
        details_response = details_request.execute()
        detail_items: Iterable[Dict[str, Any]] = details_response.get("items", [])

        for item in detail_items:
            record = _build_video_record(item)
            if record is None:
                continue
            videos.append(record)
            if limit is not None and len(videos) >= limit:
                return videos

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def _resolve_uploads_playlist_id(service: Any, channel_id: Optional[str]) -> Optional[str]:
    if channel_id:
        channel_request = service.channels().list(
            part="contentDetails",
            id=channel_id,
            maxResults=1,
        )
    else:
        channel_request = service.channels().list(
            part="contentDetails",
            mine=True,
            maxResults=1,
        )
    channel_response = channel_request.execute()
    items = channel_response.get("items", [])
    if not items:
        return None
    uploads = (
        items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    return uploads


def _build_video_record(item: Dict[str, Any]) -> Optional[VideoRecord]:
    video_id = item.get("id")
    snippet = item.get("snippet", {})
    status = item.get("status", {})
    content_details = item.get("contentDetails", {})
    file_details = item.get("fileDetails", {})
    if not video_id or not snippet:
        return None

    file_size = None
    if isinstance(file_details, dict):
        file_size = file_details.get("fileSize")
        if file_size is not None:
            try:
                file_size = int(file_size)
            except (TypeError, ValueError):
                file_size = None

    return VideoRecord(
        video_id=str(video_id),
        title=str(snippet.get("title", "")),
        visibility=str(status.get("privacyStatus", "")),
        duration=str(content_details.get("duration", "")),
        file_size_bytes=file_size,
    )


def apply_filters(
    videos: Iterable[VideoRecord],
    visibility_filter: Optional[Sequence[str]] = None,
    title_keywords: Optional[Sequence[str]] = None,
) -> List[VideoRecord]:
    result: List[VideoRecord] = []
    for record in videos:
        if visibility_filter and record.visibility not in visibility_filter:
            continue
        if title_keywords and not any(
            keyword.lower() in record.title.lower() for keyword in title_keywords
        ):
            continue
        result.append(record)
    return result


def format_file_size(bytes_value: Optional[int]) -> str:
    if bytes_value is None:
        return "unknown"
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(bytes_value)
    for unit in units:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


def write_csv(path: Path, records: Sequence[VideoRecord]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["title", "visibility", "duration", "file_size_bytes", "file_size_human", "video_url"]
        )
        for record in records:
            writer.writerow(
                [
                    record.title,
                    record.visibility,
                    record.duration,
                    record.file_size_bytes or "",
                    format_file_size(record.file_size_bytes),
                    record.video_url,
                ]
            )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )

    service = get_youtube_service(
        client_secrets_file=str(args.client_secrets_file),
        token_file=str(args.token_file),
    )

    videos = fetch_channel_videos(
        service=service,
        channel_id=args.channel_id,
        max_results=args.max_results,
        limit=args.limit,
    )

    # Apply basic filters; adjust collections below for different behaviour.
    visibility_filter = ["public"]  # modify in code if needed
    title_keywords: Optional[Sequence[str]] = None
    filtered_videos = apply_filters(
        videos,
        visibility_filter=visibility_filter,
        title_keywords=title_keywords,
    )

    if not filtered_videos:
        _logger.info("No videos matched the current filters.")
        return 0

    if args.output_csv:
        write_csv(args.output_csv, filtered_videos)
        _logger.info("Wrote %s records to %s", len(filtered_videos), args.output_csv)

    for record in filtered_videos:
        _logger.info(
            "%s | %s | %s | %s",
            record.title,
            record.visibility,
            format_file_size(record.file_size_bytes),
            record.video_url,
        )
    _logger.info(
        "Listed %s videos (filtered from %s total).",
        len(filtered_videos),
        len(videos),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
