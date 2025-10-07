"""Configuration constants for the YouTube connector."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

PACKAGE_ROOT = Path(__file__).resolve().parent
CONNECTOR_ROOT = PACKAGE_ROOT
LOG_FILE_PATH = PACKAGE_ROOT.parent / "youtube_upload.log"
DEFAULT_MANIFEST_PATH = PACKAGE_ROOT / "video_manifest.csv"

DEFAULT_CLIENT_SECRETS_FILE = "credentials.json"
DEFAULT_TOKEN_FILE = "token.json"

OAUTH_SCOPES: Tuple[str, ...] = (
    "https://www.googleapis.com/auth/youtube.force-ssl",
)

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

DEFAULT_PLAYLIST_ID = "PL1234567890ABCDEFGHIJ"
VIDEO_EXTENSIONS: Tuple[str, ...] = (".mp4", ".mov", ".avi", ".mkv", ".m4v")

DEFAULT_CATEGORY_ID = "22"
DEFAULT_PRIVACY_STATUS = "private"
