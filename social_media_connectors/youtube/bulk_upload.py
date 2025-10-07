"""CSV-driven bulk upload workflow."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from . import config, upload
from .client import get_youtube_service
from .logging_utils import get_logger

_logger = get_logger(__name__)

REQUIRED_COLUMNS = {"video_name", "video_location", "playlist_id"}


@dataclass(frozen=True)
class UploadContext:
    """Context information about a CSV row being processed."""
    row_number: int
    video_name: str
    video_location: str


@dataclass
class UploadSummary:
    """Aggregate outcome for a CSV upload batch."""
    successes: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def has_errors(self) -> bool:
        """Return True when any errors were recorded."""
        return bool(self.errors)

    def as_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the summary."""
        return {"successes": self.successes, "errors": self.errors}

    def to_json(self) -> str:
        """Return a JSON string representation of the summary."""
        return json.dumps(self.as_dict(), ensure_ascii=False, indent=2)


def process_csv_uploads(
    csv_path: str | Path,
    *,
    client_secrets_file: str = config.DEFAULT_CLIENT_SECRETS_FILE,
    token_file: str = config.DEFAULT_TOKEN_FILE,
    default_description: str = "",
    default_privacy_status: str = config.DEFAULT_PRIVACY_STATUS,
    default_category_id: str = config.DEFAULT_CATEGORY_ID,
    default_playlist_id: Optional[str] = None,
    default_tags: Sequence[str] | None = None,
) -> UploadSummary:
    """Process uploads described in a CSV file.

    The CSV is updated in-place with an ``uploaded_video_id`` column capturing
    the resulting YouTube video ID (or the string ``"None"`` when an error
    occurs) so that interrupted batches can be resumed later.
    """
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Expected CSV file but found directory: {path}")

    service = get_youtube_service(
        client_secrets_file=client_secrets_file,
        token_file=token_file,
    )

    summary = UploadSummary()
    _logger.info("Starting bulk upload from %s", path)

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        fieldnames = reader.fieldnames

    _ensure_required_columns(fieldnames)
    fieldnames = list(fieldnames or [])
    header_requires_write = "uploaded_video_id" not in fieldnames
    if header_requires_write:
        fieldnames.append("uploaded_video_id")

    for row in rows:
        row.setdefault("uploaded_video_id", "")

    csv_written = False

    for index, row in enumerate(rows, start=2):
        context = _context_from_row(index, row)
        existing_id = _extract_uploaded_id(row.get("uploaded_video_id"))
        if existing_id:
            summary.successes.append(
                {
                    "row_number": context.row_number,
                    "video_name": context.video_name,
                    "video_location": context.video_location,
                    "video_id": existing_id,
                    "playlist_id": _clean_value(row.get("playlist_id")) or "",
                    "status": "skipped",
                }
            )
            _logger.info(
                "Skipping row %s; already uploaded with video ID %s",
                index,
                existing_id,
            )
            continue

        try:
            result = _handle_csv_row(
                service=service,
                row=row,
                context=context,
                default_description=default_description,
                default_privacy_status=default_privacy_status,
                default_category_id=default_category_id,
                default_playlist_id=default_playlist_id,
                default_tags=default_tags,
            )
            row["uploaded_video_id"] = result["video_id"]
            summary.successes.append(result)
        except upload.YouTubeUploadLimitError as exc:
            row["uploaded_video_id"] = "None"
            summary.errors.append(_format_error(context, exc))
            _logger.warning(
                "Quota exhausted while processing row %s; stopping batch",
                index,
            )
            _write_updated_csv(path, fieldnames, rows)
            csv_written = True
            break
        except Exception as exc:  # pylint: disable=broad-except
            row["uploaded_video_id"] = "None"
            summary.errors.append(_format_error(context, exc))
            _logger.error(
                "Failed to process row %s (%s): %s",
                index,
                context.video_name,
                exc,
            )
        else:
            _write_updated_csv(path, fieldnames, rows)
            csv_written = True
            continue
        # Write updates before continuing after non-quota errors.
        _write_updated_csv(path, fieldnames, rows)
        csv_written = True

    _logger.info(
        "Completed bulk upload: %s successes, %s errors",
        len(summary.successes),
        len(summary.errors),
    )

    if header_requires_write and not csv_written:
        _write_updated_csv(path, fieldnames, rows)

    return summary


def _context_from_row(row_number: int, row: Dict[str, Any]) -> UploadContext:
    video_name = _clean_value(row.get("video_name")) or f"Row{row_number}"
    video_location = _clean_value(row.get("video_location")) or ""
    return UploadContext(
        row_number=row_number,
        video_name=video_name,
        video_location=video_location,
    )


def _ensure_required_columns(columns: Iterable[str] | None) -> None:
    if columns is None:
        raise ValueError("CSV file must include a header row")
    missing = REQUIRED_COLUMNS - set(columns)
    if missing:
        raise ValueError(f"CSV file missing required columns: {sorted(missing)}")


def _handle_csv_row(
    *,
    service: Any,
    row: Dict[str, Any],
    context: UploadContext,
    default_description: str,
    default_privacy_status: str,
    default_category_id: str,
    default_playlist_id: Optional[str],
    default_tags: Sequence[str] | None,
) -> Dict[str, Any]:
    video_location = _clean_value(row.get("video_location"))
    if not video_location:
        raise ValueError("CSV row is missing video_location")
    video_path = Path(video_location).expanduser()

    playlist_id = (
        _clean_value(row.get("playlist_id")) or default_playlist_id or ""
    )
    title = _clean_value(row.get("title")) or context.video_name
    description = _clean_value(row.get("description")) or default_description
    privacy_status = (
        _clean_value(row.get("privacy_status")) or default_privacy_status
    )
    category_id = _clean_value(row.get("category_id")) or default_category_id
    playlist_position = _parse_int(_clean_value(row.get("playlist_position")))
    tags = _resolve_tags(row.get("tags")) or (
        list(default_tags) if default_tags else None
    )
    notify_subscribers = (
        _clean_value(row.get("notify_subscribers")) or ""
    ).lower() in {"1", "true", "yes"}

    if playlist_id:
        result = upload.upload_video_and_add_to_playlist(
            service=service,
            video_path=video_path,
            title=title,
            description=description,
            playlist_id=playlist_id,
            category_id=category_id,
            privacy_status=privacy_status,
            tags=tags,
            playlist_position=playlist_position,
            notify_subscribers=notify_subscribers,
        )
        return {
            "row_number": context.row_number,
            "video_name": context.video_name,
            "video_location": str(video_path),
            "video_id": result["video"]["id"],
            "playlist_id": playlist_id,
            "playlist_item_id": result["playlist_item"]["id"],
        }

    video_id = upload.upload_video(
        service=service,
        video_path=video_path,
        title=title,
        description=description,
        category_id=category_id,
        privacy_status=privacy_status,
        tags=tags,
        notify_subscribers=notify_subscribers,
    )
    return {
        "row_number": context.row_number,
        "video_name": context.video_name,
        "video_location": str(video_path),
        "video_id": video_id,
        "playlist_id": "",
    }


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _parse_int(value: str | None) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid integer value: {value}") from None


def _resolve_tags(raw_tags: Any) -> List[str]:
    cleaned = _clean_value(raw_tags)
    if not cleaned:
        return []
    return [tag.strip() for tag in cleaned.split(",") if tag.strip()]


def _format_error(context: UploadContext, exc: Exception) -> Dict[str, Any]:
    return {
        "row_number": context.row_number,
        "video_name": context.video_name,
        "video_location": context.video_location,
        "error": str(exc),
        "exception_type": exc.__class__.__name__,
    }


def _write_updated_csv(
    path: Path,
    fieldnames: Sequence[str],
    rows: Sequence[Dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _extract_uploaded_id(value: Any) -> str | None:
    cleaned = _clean_value(value)
    if not cleaned:
        return None
    if cleaned.lower() == "none":
        return None
    return cleaned
