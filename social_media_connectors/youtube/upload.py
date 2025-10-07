"""YouTube upload helpers and quota-aware error handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Set

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config, playlists
from .logging_utils import get_logger

_logger = get_logger(__name__)

_UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB
_KNOWN_QUOTA_REASONS: Set[str] = {
    "quotaExceeded",
    "dailyLimitExceeded",
    "userRateLimitExceeded",
    "rateLimitExceeded",
}


class YouTubeUploadLimitError(RuntimeError):
    """Raised when the YouTube API reports a quota exhaustion condition."""


def upload_video(
    service: Any,
    video_path: str | Path,
    title: str,
    description: str,
    *,
    category_id: str = config.DEFAULT_CATEGORY_ID,
    privacy_status: str = config.DEFAULT_PRIVACY_STATUS,
    tags: Sequence[str] | None = None,
    notify_subscribers: bool = False,
) -> str:
    """Upload a single video and return the resulting YouTube video ID."""
    path = Path(video_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Video file not found: {path}")

    snippet: Dict[str, Any] = {
        "title": title,
        "description": description,
        "categoryId": category_id,
    }
    if tags:
        snippet["tags"] = list(tags)

    status = {"privacyStatus": privacy_status, "selfDeclaredMadeForKids": False}

    media_body = MediaFileUpload(
        filename=str(path),
        chunksize=_UPLOAD_CHUNK_SIZE,
        resumable=True,
    )

    request = service.videos().insert(
        part="snippet,status",
        body={
            "snippet": snippet,
            "status": status,
            "notifySubscribers": notify_subscribers,
        },
        media_body=media_body,
    )

    _logger.info("Starting upload for %s", path)
    try:
        response = _upload_request_until_complete(request)
    except HttpError as exc:
        _handle_http_error(exc)
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube API response missing video ID")
    _logger.info("Upload complete for %s (video_id=%s)", path, video_id)
    return str(video_id)


def upload_video_and_add_to_playlist(
    service: Any,
    video_path: str | Path,
    title: str,
    description: str,
    playlist_id: str,
    *,
    category_id: str = config.DEFAULT_CATEGORY_ID,
    privacy_status: str = config.DEFAULT_PRIVACY_STATUS,
    tags: Sequence[str] | None = None,
    playlist_position: Optional[int] = None,
    notify_subscribers: bool = False,
) -> Dict[str, Dict[str, str]]:
    """Upload a video and insert it into the specified playlist."""
    video_id = upload_video(
        service=service,
        video_path=video_path,
        title=title,
        description=description,
        category_id=category_id,
        privacy_status=privacy_status,
        tags=tags,
        notify_subscribers=notify_subscribers,
    )
    playlist_item_id = playlists.add_video_to_playlist(
        service=service,
        playlist_id=playlist_id,
        video_id=video_id,
        position=playlist_position,
    )
    _logger.info(
        "Added video %s to playlist %s (playlist_item_id=%s)",
        video_id,
        playlist_id,
        playlist_item_id,
    )
    return {
        "video": {"id": video_id, "title": title},
        "playlist_item": {"id": playlist_item_id, "playlist_id": playlist_id},
    }


def _upload_request_until_complete(request: Any) -> Dict[str, Any]:
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response


def _handle_http_error(exc: HttpError) -> None:
    message = getattr(exc, "message", "") or str(exc)
    reasons = _extract_error_reasons(exc)
    if _is_quota_error(reasons, message):
        raise YouTubeUploadLimitError(message) from exc
    raise exc


def _extract_error_reasons(exc: HttpError) -> Set[str]:
    reasons: Set[str] = set()
    content: bytes | str | None = getattr(exc, "content", None)
    if not content:
        return reasons
    try:
        if isinstance(content, bytes):
            parsed = json.loads(content.decode("utf-8"))
        else:
            parsed = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return reasons
    errors: Iterable[Dict[str, Any]] = (
        parsed.get("error", {}).get("errors", [])
        if isinstance(parsed, dict)
        else []
    )
    for error in errors:
        reason = error.get("reason")
        if reason:
            reasons.add(str(reason))
    return reasons


def _is_quota_error(reasons: Set[str], message: str) -> bool:
    if reasons & _KNOWN_QUOTA_REASONS:
        return True
    lowered = message.lower()
    return "quota" in lowered or "rate limit" in lowered
