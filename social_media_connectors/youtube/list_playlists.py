"""Utilities and CLI for listing YouTube playlists belonging to a channel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from .client import get_youtube_service
from .logging_utils import get_logger
from .cli.common import add_auth_arguments

_logger = get_logger(__name__)


def fetch_playlists(
    service: Resource,
    *,
    channel_id: str | None = None,
    page_size: int = 50,
) -> List[Dict[str, Any]]:
    """Return metadata for playlists accessible to the authenticated user."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    request_kwargs: Dict[str, Any] = {
        "part": "snippet,contentDetails",
        "maxResults": min(page_size, 50),
    }
    if channel_id:
        request_kwargs["channelId"] = channel_id
    else:
        request_kwargs["mine"] = True

    request = service.playlists().list(**request_kwargs)
    playlists: List[Dict[str, Any]] = []

    while request is not None:
        response = request.execute()
        for item in response.get("items", []):
            snippet = item.get("snippet") or {}
            content_details = item.get("contentDetails") or {}
            playlists.append(
                {
                    "id": item.get("id", ""),
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "item_count": content_details.get("itemCount", 0),
                }
            )
        request = service.playlists().list_next(request, response)

    _logger.info(
        "Fetched %s playlists%s",
        len(playlists),
        f" for channel {channel_id}" if channel_id else "",
    )
    return playlists


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the playlist fetcher."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch all playlists for the authenticated channel or a specific "
            "channel ID."
        )
    )
    parser.add_argument(
        "--channel-id",
        help=(
            "Explicit channel ID to query. Defaults to the channel associated "
            "with the provided OAuth token."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=50,
        help="Number of items to request per API page (max 50).",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the playlist metadata as JSON.",
    )
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Suppress console output of playlist summaries.",
    )
    add_auth_arguments(parser)
    return parser.parse_args(argv)


def _write_output(path: str, data: List[Dict[str, Any]]) -> Path:
    output_path = Path(path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point when invoking the module as a script."""
    args = parse_args(argv)
    service = get_youtube_service(
        client_secrets_file=args.client_secrets,
        token_file=args.token_file,
    )

    try:
        playlists = fetch_playlists(
            service=service,
            channel_id=args.channel_id,
            page_size=args.page_size,
        )
    except HttpError as exc:
        _logger.error("YouTube API error while fetching playlists: %s", exc)
        print(f"Failed to fetch playlists: {exc}")
        return 1
    except Exception as exc:  # pylint: disable=broad-except
        _logger.error("Unexpected error fetching playlists: %s", exc, exc_info=True)
        print(f"Unexpected error: {exc}")
        return 1

    if args.output:
        output_path = _write_output(args.output, playlists)
        print(f"Wrote {len(playlists)} playlists to {output_path}")

    if not args.no_console:
        if playlists:
            for entry in playlists:
                title = entry.get("title") or "(untitled playlist)"
                playlist_id = entry.get("id") or "(no id)"
                count = entry.get("item_count", 0)
                print(f"{playlist_id} | {count:>3} videos | {title}")
        else:
            print("No playlists found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
