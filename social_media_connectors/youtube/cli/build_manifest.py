"""CLI entry point for generating upload manifests."""

from __future__ import annotations

import argparse
from typing import Sequence

from .. import config, manifest
from .common import add_auth_arguments  # imported for parity across CLIs (unused)

__all__ = ["main"]  # silence lint for unused re-export via add_auth_arguments


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build a YouTube upload manifest from a directory of videos.",
    )
    parser.add_argument("directory", help="Directory containing video files.")
    parser.add_argument(
        "--output",
        help="Path to write the manifest CSV (default: package default).",
    )
    parser.add_argument(
        "--playlist-id",
        default=config.DEFAULT_PLAYLIST_ID,
        help="Playlist ID to include in the manifest rows.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=list(config.VIDEO_EXTENSIONS),
        help="File extensions to include (default: common video formats).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search for videos within subdirectories.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Execute the build-manifest CLI."""
    args = parse_args(argv)
    output_path = manifest.create_manifest_from_directory(
        directory=args.directory,
        output=args.output,
        playlist_id=args.playlist_id,
        extensions=args.extensions,
        recursive=args.recursive,
    )
    print(f"Wrote manifest to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
