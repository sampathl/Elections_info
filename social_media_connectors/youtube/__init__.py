"""YouTube connector package exposing high-level entry points."""

from __future__ import annotations

from .bulk_upload import UploadSummary, process_csv_uploads
from .client import get_youtube_service
from .manifest import ManifestRow, create_manifest_from_directory
from .upload import (
    YouTubeUploadLimitError,
    upload_video,
    upload_video_and_add_to_playlist,
)

__all__ = [
    "ManifestRow",
    "UploadSummary",
    "YouTubeUploadLimitError",
    "create_manifest_from_directory",
    "get_youtube_service",
    "process_csv_uploads",
    "upload_video",
    "upload_video_and_add_to_playlist",
]
