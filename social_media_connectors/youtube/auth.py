"""OAuth credential management for YouTube API access."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from . import config
from .logging_utils import get_logger

_logger = get_logger(__name__)
_CREDENTIAL_CACHE: Dict[Tuple[str, str], Credentials] = {}


def get_credentials(
    client_secrets_file: str = config.DEFAULT_CLIENT_SECRETS_FILE,
    token_file: str = config.DEFAULT_TOKEN_FILE,
) -> Credentials:
    """Return valid OAuth credentials, refreshing or re-authorising as necessary."""
    secrets_path = Path(client_secrets_file).expanduser().resolve()
    token_path = Path(token_file).expanduser().resolve()
    cache_key = (str(secrets_path), str(token_path))

    cached = _CREDENTIAL_CACHE.get(cache_key)
    if cached and cached.valid:
        return cached

    credentials = _load_credentials_from_disk(token_path)
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            _logger.info("Refreshed OAuth credentials for %s", token_path)
            _save_credentials(token_path, credentials)
        except RefreshError as exc:
            _logger.warning(
                "Failed to refresh credentials at %s: %s; re-running OAuth flow",
                token_path,
                exc,
            )
            credentials = None

    if not credentials or not credentials.valid:
        credentials = _run_interactive_flow(secrets_path)
        _save_credentials(token_path, credentials)

    _CREDENTIAL_CACHE[cache_key] = credentials
    return credentials


def _load_credentials_from_disk(token_path: Path) -> Credentials | None:
    if not token_path.exists():
        return None
    try:
        credentials = Credentials.from_authorized_user_file(
            str(token_path), scopes=config.OAUTH_SCOPES
        )
        _logger.info("Loaded cached credentials from %s", token_path)
        return credentials
    except Exception as exc:  # pylint: disable=broad-except
        _logger.error(
            "Unable to load credentials from %s: %s", token_path, exc
        )
        return None


def _save_credentials(token_path: Path, credentials: Credentials) -> None:
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    _logger.info("Persisted credentials to %s", token_path)


def _run_interactive_flow(secrets_path: Path) -> Credentials:
    if not secrets_path.exists():
        raise FileNotFoundError(
            f"Client secrets file not found: {secrets_path}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(secrets_path), scopes=config.OAUTH_SCOPES
    )

    for port in (8080, 0):
        try:
            credentials = flow.run_local_server(
                port=port,
                access_type="offline",
                prompt="consent",
            )
            _logger.info(
                "Completed OAuth flow via local server on port %s", port
            )
            return credentials
        except OSError as exc:
            _logger.warning(
                "Local server authentication on port %s failed: %s; "
                "falling back to next method",
                port,
                exc,
            )

    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print("Please visit this URL to authorise the application:\n")
    print(auth_url)
    print()
    code = input("Enter the authorisation code: ").strip()
    flow.fetch_token(code=code)
    credentials = flow.credentials
    _logger.info("Completed manual OAuth flow via copy/paste code entry")
    return credentials
