"""CLI entry point for creating YouTube playlists."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from .. import config, playlists
from ..client import get_youtube_service
from ..logging_utils import get_logger
from .common import add_auth_arguments

_logger = get_logger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Create YouTube playlists from provided titles or a constituency file.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--titles",
        nargs="+",
        help="One or more playlist titles to create.",
    )
    group.add_argument(
        "--constituency-file",
        help="Path to a text file containing 'Name - URL' lines.",
    )
    parser.add_argument(
        "--descriptions",
        nargs="*",
        help="Descriptions corresponding to each title (optional).",
    )
    parser.add_argument(
        "--start-from",
        help="When using a constituency file, start processing from this entry.",
    )
    parser.add_argument(
        "--privacy",
        default=config.DEFAULT_PRIVACY_STATUS,
        help="Privacy status for new playlists.",
    )
    parser.add_argument(
        "--default-description",
        default="",
        help="Fallback description when none is provided.",
    )
    parser.add_argument(
        "--results-output",
        help="Path to store the playlist creation results JSON.",
    )
    add_auth_arguments(parser)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the playlist creation CLI."""
    args = parse_args(argv)
    service = get_youtube_service(
        client_secrets_file=args.client_secrets,
        token_file=args.token_file,
    )

    if args.constituency_file:
        titles, descriptions = playlists.parse_constituency_file(
            file_path=args.constituency_file,
            start_from=args.start_from,
        )
    else:
        titles = args.titles or []
        descriptions = args.descriptions
        if descriptions and len(descriptions) != len(titles):
            print("Number of descriptions must match the number of titles.")
            return 1

    try:
        results = playlists.create_playlists(
            service=service,
            titles=titles,
            descriptions=descriptions,
            privacy=args.privacy,
            default_description=args.default_description,
        )
        failures = 0
    except Exception as exc:  # pylint: disable=broad-except
        _logger.error("Failed to create playlists: %s", exc, exc_info=True)
        results = []
        failures = len(titles)
        print(f"Playlist creation failed: {exc}")

    output_path = _resolve_output_path(args.results_output)
    playlists.save_results_to_file(results, str(output_path))
    print(
        f"Created {len(results)} playlists; failures: {failures}. "
        f"Results saved to {output_path}"
    )
    return 0 if failures == 0 else 1


def _resolve_output_path(candidate: str | None) -> Path:
    if candidate:
        return Path(candidate).expanduser().resolve()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return Path(
        f"playlist_creation_results_{timestamp}.json"
    ).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
