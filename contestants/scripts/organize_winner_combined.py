"""Reorganize combined winner videos into id1/language folders.

This script takes videos that currently live in a single directory (e.g.
`static/Bihar/winner_c`) and moves them into an `id1/<language>/` hierarchy.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def reorganize_combined_videos(
    base_dir: Path,
    dry_run: bool = False,
) -> None:
    """Move combined videos into an id1/language directory structure."""
    files = [path for path in base_dir.iterdir() if path.is_file()]
    for src_path in sorted(files):
        stem_parts = src_path.stem.split("_")
        if len(stem_parts) < 3:
            print(f"[warn] Unexpected filename format: {src_path.name}")
            continue

        id1, _, language = stem_parts[:3]
        target_dir = base_dir / id1 / language
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = target_dir / src_path.name
        if target_path.exists():
            raise FileExistsError(
                f"Target already exists: {target_path}. "
                "Resolve the conflict and re-run the script."
            )

        if dry_run:
            print(f"[dry-run] {src_path} -> {target_path}")
        else:
            shutil.move(str(src_path), str(target_path))
            print(f"[moved] {src_path} -> {target_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reorganize combined winner videos by id1 and language.",
    )

    default_base = (
        Path(__file__).resolve().parents[2]
        / "static"
        / "Bihar"
        / "winner_c"
    )

    parser.add_argument(
        "--base-dir",
        type=Path,
        default=default_base,
        help=f"Directory holding the combined winner files (default: {default_base})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without moving any files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reorganize_combined_videos(args.base_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
