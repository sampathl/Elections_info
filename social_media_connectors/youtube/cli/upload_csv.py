"""CLI entry point for processing CSV uploads."""

from __future__ import annotations

import argparse
from typing import Sequence

from .. import config
from ..bulk_upload import process_csv_uploads
from ..logging_utils import get_logger
from .common import add_auth_arguments

_logger = get_logger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Upload videos to YouTube based on a CSV manifest.",
    )
    parser.add_argument("csv", help="Path to the CSV manifest file.")
    parser.add_argument(
        "--default-description",
        default="",
        help="Fallback description when the CSV omits one.",
    )
    parser.add_argument(
        "--privacy",
        default=config.DEFAULT_PRIVACY_STATUS,
        help="Default privacy status for uploads.",
    )
    parser.add_argument(
        "--category-id",
        default=config.DEFAULT_CATEGORY_ID,
        help="Default video category ID.",
    )
    parser.add_argument(
        "--default-playlist",
        help="Fallback playlist ID when the CSV omits one.",
    )
    parser.add_argument(
        "--default-tags",
        nargs="*",
        help="Tags to apply when the CSV omits them.",
    )
    add_auth_arguments(parser)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the upload CSV CLI."""
    args = parse_args(argv)
    summary = process_csv_uploads(
        csv_path=args.csv,
        client_secrets_file=args.client_secrets,
        token_file=args.token_file,
        default_description=args.default_description,
        default_privacy_status=args.privacy,
        default_category_id=args.category_id,
        default_playlist_id=args.default_playlist,
        default_tags=args.default_tags,
    )
    print(summary.to_json())
    if summary.has_errors():
        _logger.warning(
            "Bulk upload completed with %s errors", len(summary.errors)
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
