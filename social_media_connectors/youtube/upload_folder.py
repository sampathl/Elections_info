"""Upload every video in a folder to the configured YouTube channel.

This script reuses the channel credentials and defaults defined in
``social_media_connectors.youtube.config``. By default it uploads each
video it finds to the channel using the filename stem as the title.

Example usage:

    python -m social_media_connectors.youtube.upload_folder /path/to/videos \
        --description-template "Highlights for {stem}" \
        --tags elections bihar
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

try:
    from . import config, upload
    from .client import get_youtube_service
    from .logging_utils import get_logger
except ImportError:  # pragma: no cover - allow running as a script
    import sys as _sys
    from pathlib import Path as _Path

    _PACKAGE_ROOT = _Path(__file__).resolve().parents[1]
    _sys.path.append(str(_PACKAGE_ROOT.parent))

    from social_media_connectors.youtube import config, upload
    from social_media_connectors.youtube.client import get_youtube_service
    from social_media_connectors.youtube.logging_utils import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class UploadResult:
    path: Path
    title: str
    video_id: Optional[str]
    error: Optional[Exception] = None

    @property
    def succeeded(self) -> bool:
        return self.video_id is not None and self.error is None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload all videos from a folder to the configured YouTube channel.",
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="Folder containing the videos to upload.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively search for videos in subdirectories.",
    )
    parser.add_argument(
        "--client-secrets-file",
        type=Path,
        default=Path(config.DEFAULT_CLIENT_SECRETS_FILE),
        help="Path to the OAuth client secrets file.",
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=Path(config.DEFAULT_TOKEN_FILE),
        help="Path to the OAuth token file.",
    )
    parser.add_argument(
        "--title-template",
        default="{stem}",
        help="Format string for video titles (available fields: {stem}, {name}).",
    )
    parser.add_argument(
        "--description-template",
        default="",
        help="Optional description format string (fields: {stem}, {name}, {path}).",
    )
    parser.add_argument(
        "--privacy-status",
        default="private", #config.DEFAULT_PRIVACY_STATUS,
        help="YouTube privacy status (public, private, unlisted).",
    )
    parser.add_argument(
        "--category-id",
        default=config.DEFAULT_CATEGORY_ID,
        help="YouTube category ID for the uploaded videos.",
    )
    parser.add_argument(
        "--tags",
        nargs="*",
        help="Optional list of tags to apply to every video.",
    )
    parser.add_argument(
        "--playlist-id",
        help="Optional playlist ID. When provided, each upload is added to this playlist.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of videos to upload.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the videos that would be uploaded without contacting YouTube.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser.parse_args(argv)


def discover_videos(folder: Path, recursive: bool = False) -> List[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Expected folder but found file: {folder}")

    extensions = {ext.lower() for ext in config.VIDEO_EXTENSIONS}
    candidates: Iterable[Path]
    if recursive:
        candidates = (path for path in folder.rglob("*") if path.is_file())
    else:
        candidates = (path for path in folder.iterdir() if path.is_file())

    videos = sorted(
        (
            path.resolve()
            for path in candidates
            if path.suffix.lower() in extensions
        ),
        key=lambda path: path.name,
    )
    return videos


def format_title(path: Path, template: str) -> str:
    return template.format(stem=path.stem, name=path.name)


def format_description(path: Path, template: str) -> str:
    if not template:
        return ""
    return template.format(stem=path.stem, name=path.name, path=str(path))


def upload_folder_videos(args: argparse.Namespace) -> List[UploadResult]:
    videos = discover_videos(args.folder, recursive=args.recursive)
    if not videos:
        _logger.warning("No videos found in %s", args.folder)
        return []

    if args.limit is not None:
        videos = videos[: args.limit]

    _logger.info("Preparing to upload %s video(s)", len(videos))

    description_template = args.description_template
    tags = tuple(args.tags) if args.tags else None

    if args.dry_run:
        for path in videos:
            title = format_title(path, args.title_template)
            description = format_description(path, description_template)
            _logger.info("[DRY RUN] Would upload %s with title=%r", path, title)
            if description:
                _logger.debug("Description: %s", description)
        return []

    service = get_youtube_service(
        client_secrets_file=str(args.client_secrets_file),
        token_file=str(args.token_file),
    )

    results: List[UploadResult] = []
    for index, path in enumerate(videos, start=1):
        title = format_title(path, args.title_template)
        description = format_description(path, description_template)
        _logger.info("Uploading %s/%s: %s", index, len(videos), path)
        try:
            if args.playlist_id:
                outcome = upload.upload_video_and_add_to_playlist(
                    service=service,
                    video_path=path,
                    title=title,
                    description=description,
                    playlist_id=args.playlist_id,
                    category_id=args.category_id,
                    privacy_status=args.privacy_status,
                    tags=tags,
                )
                video_id = outcome["video"]["id"]
            else:
                video_id = upload.upload_video(
                    service=service,
                    video_path=path,
                    title=title,
                    description=description,
                    category_id=args.category_id,
                    privacy_status=args.privacy_status,
                    tags=tags,
                )
            _logger.info("Uploaded %s (video_id=%s)", path, video_id)
            results.append(
                UploadResult(
                    path=path,
                    title=title,
                    video_id=video_id,
                )
            )
        except Exception as exc:  # pylint: disable=broad-except
            _logger.error("Failed to upload %s: %s", path, exc)
            results.append(
                UploadResult(
                    path=path,
                    title=title,
                    video_id=None,
                    error=exc,
                )
            )
            if isinstance(exc, upload.YouTubeUploadLimitError):
                _logger.warning("Quota exhausted; stopping remaining uploads.")
                break
    return results


def summarise_results(results: Sequence[UploadResult]) -> None:
    successes = [result for result in results if result.succeeded]
    failures = [result for result in results if not result.succeeded]

    _logger.info("Upload summary: %s successes, %s failures", len(successes), len(failures))
    if successes:
        success_lines = "\n".join(
            f"  - {result.path} -> {result.video_id}"
            for result in successes
        )
        _logger.info("Successful uploads:\n%s", success_lines)
    if failures:
        failure_lines = "\n".join(
            f"  - {result.path}: {result.error}"
            for result in failures
        )
        _logger.error("Failed uploads:\n%s", failure_lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )
    try:
        results = upload_folder_videos(args)
        summarise_results(results)
    except Exception as exc:  # pylint: disable=broad-except
        _logger.error("Fatal error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
