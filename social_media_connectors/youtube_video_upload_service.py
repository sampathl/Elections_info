"""Utility for uploading videos to YouTube with quota-aware error handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .youtube_playlist_script_scripts import add_video_to_playlist, build_youtube_service


class YouTubeUploadLimitError(RuntimeError):
    """Raised when a video upload fails because the API quota has been exhausted."""


_QUOTA_REASONS = {
    "quotaExceeded",
    "dailyLimitExceeded",
    "userRateLimitExceeded",
    "rateLimitExceeded",
    "RESOURCE_EXHAUSTED",
}

_QUOTA_REASON_KEYWORDS = {
    "quota",
    "rate limit",
    "resource exhausted",
    "daily limit",
}


def upload_video_with_quota_handling(
    video_path: str,
    title: str,
    description: str = "",
    category_id: str = "22",
    privacy_status: str = "private",
    tags: Optional[Sequence[str]] = None,
    client_secrets_file: str = "credentials.json",
    token_file: str = "token.json",
    youtube=None,
) -> str:
    """Upload a video to YouTube and return its ID.

    Raises:
        FileNotFoundError: if the video file cannot be located.
        YouTubeUploadLimitError: if the upload fails due to API quota limits.
        HttpError: if the YouTube API returns an error unrelated to quota limits.
        RuntimeError: if the upload completes but no video ID is returned.
    """

    path = Path(video_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    service = youtube or build_youtube_service(
        client_secrets_file=client_secrets_file,
        token_file=token_file,
    )

    body: Dict[str, Any] = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }
    if tags:
        body["snippet"]["tags"] = list(tags)

    media = MediaFileUpload(str(path), chunksize=-1, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    try:
        response = _upload_request_until_complete(request)
    except HttpError as exc:
        if _is_quota_error(exc):
            raise YouTubeUploadLimitError("YouTube API quota exceeded for video upload") from exc
        raise

    video_id = response.get("id") if isinstance(response, dict) else None
    if not video_id:
        raise RuntimeError("Upload completed but no video ID returned by the API")
    return video_id


def upload_video_and_add_to_playlist(
    video_path: str,
    title: str,
    playlist_id: str,
    description: str = "",
    category_id: str = "22",
    privacy_status: str = "private",
    tags: Optional[Sequence[str]] = None,
    playlist_position: Optional[int] = None,
    client_secrets_file: str = "credentials.json",
    token_file: str = "token.json",
    youtube=None,
) -> Dict[str, Dict[str, str]]:
    """Upload a video and add it to a playlist, returning both operation results."""

    service = youtube or build_youtube_service(
        client_secrets_file=client_secrets_file,
        token_file=token_file,
    )

    video_id = upload_video_with_quota_handling(
        video_path=video_path,
        title=title,
        description=description,
        category_id=category_id,
        privacy_status=privacy_status,
        tags=tags,
        client_secrets_file=client_secrets_file,
        token_file=token_file,
        youtube=service,
    )

    playlist_item_id = add_video_to_playlist(
        playlist_id=playlist_id,
        video_id=video_id,
        position=playlist_position,
        client_secrets_file=client_secrets_file,
        token_file=token_file,
        youtube=service,
    )

    return {
        "upload": {"video_id": video_id},
        "playlist": {"playlist_item_id": playlist_item_id},
    }


def _upload_request_until_complete(request) -> Dict[str, Any]:
    """Execute a resumable upload request until completion and return the response."""
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response


def _is_quota_error(error: HttpError) -> bool:
    reasons = _extract_error_reasons(error)
    for reason in reasons:
        if reason in _QUOTA_REASONS:
            return True
        lowered = reason.lower()
        if any(keyword in lowered for keyword in _QUOTA_REASON_KEYWORDS):
            return True
    return False


def _extract_error_reasons(error: HttpError) -> Sequence[str]:
    """Extract error reason strings from a YouTube API HttpError."""
    content = getattr(error, "content", b"")
    if isinstance(content, bytes):
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError:
            return []
    else:
        decoded = str(content)

    try:
        payload = json.loads(decoded)
    except (TypeError, ValueError):
        return []

    error_obj = payload.get("error")
    reasons = []
    if isinstance(error_obj, dict):
        errors = error_obj.get("errors")
        if isinstance(errors, list):
            for item in errors:
                if isinstance(item, dict):
                    reason = item.get("reason")
                    if isinstance(reason, str):
                        reasons.append(reason)
        status = error_obj.get("status")
        if isinstance(status, str):
            reasons.append(status)
        message = error_obj.get("message")
        if isinstance(message, str):
            reasons.append(message)
    return reasons
