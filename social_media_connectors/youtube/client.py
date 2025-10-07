"""YouTube API client construction utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

from googleapiclient.discovery import Resource, build

from . import config
from .auth import get_credentials
from .logging_utils import get_logger

_logger = get_logger(__name__)
_SERVICE_CACHE: Dict[Tuple[str, str], Resource] = {}


def get_youtube_service(
    client_secrets_file: str = config.DEFAULT_CLIENT_SECRETS_FILE,
    token_file: str = config.DEFAULT_TOKEN_FILE,
) -> Resource:
    """Return a cached YouTube Data API client."""
    secrets_path = Path(client_secrets_file).expanduser().resolve()
    token_path = Path(token_file).expanduser().resolve()
    cache_key = (str(secrets_path), str(token_path))

    service = _SERVICE_CACHE.get(cache_key)
    if service is not None:
        return service

    credentials = get_credentials(
        client_secrets_file=str(secrets_path),
        token_file=str(token_path),
    )
    service = build(
        config.API_SERVICE_NAME,
        config.API_VERSION,
        credentials=credentials,
        cache_discovery=False,
    )
    _SERVICE_CACHE[cache_key] = service
    _logger.info(
        "Created YouTube service for secrets=%s token=%s",
        secrets_path,
        token_path,
    )
    return service
