"""Batch narration generator for English and Hindi videos from a CSV."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PARENT = PROJECT_ROOT.parent
for path in (PROJECT_PARENT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - runtime dependency notice
    raise SystemExit(
        "pandas is required for this script. Install it with `pip install pandas`."
    ) from exc

from winners.audio_pipeline.pipelines.narration import NarrationPipeline
from winners.entities.candidate_record import CandidateRecord
from winners.video_pipeline.paths import configure_output_year

REQUIRED_COLUMNS: Iterable[str] = (
    "Constituency_ID",
    "Candidate_ID",
    "Constituency",
    "Election_Type",
    "Candidate_name",
    "Party",
    "Criminal_Cases",
    "Education",
    "education_details",
    "age",
    "total_assets",
    "assets_description",
    "total_liabilities",
    "liabilities_description",
    "voter_info",
    "url",
)


def _sanitize(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _row_to_record(row: Dict[str, object], *, year: str = "") -> CandidateRecord:
    record = CandidateRecord(
        constituency_id=_sanitize(row.get("Constituency_ID", "")),
        candidate_id=_sanitize(row.get("Candidate_ID", "")),
        constituency=_sanitize(row.get("Constituency", "")),
        election_type=_sanitize(row.get("Election_Type", "")),
        candidate_name=_sanitize(row.get("Candidate_name", "")),
        party=_sanitize(row.get("Party", "")),
        criminal_cases=_sanitize(row.get("Criminal_Cases", "")),
        education=_sanitize(row.get("Education", "")),
        education_details=_sanitize(row.get("education_details", "")),
        age=_sanitize(row.get("age", "")),
        total_assets=_sanitize(row.get("total_assets", "")),
        assets_description=_sanitize(row.get("assets_description", "")),
        total_liabilities=_sanitize(row.get("total_liabilities", "")),
        liabilities_description=_sanitize(row.get("liabilities_description", "")),
        voter_info=_sanitize(row.get("voter_info", "")),
        url=_sanitize(row.get("url", "")),
    )
    record.election_year = str(year).strip()
    return record


def _generate_for_locale(
    record: CandidateRecord,
    pipeline: NarrationPipeline,
    *,
    store_full_ssml: bool,
) -> None:
    assets = pipeline.build_assets(record)
    pipeline.populate_ssml(assets, wrap_with_speak=True, store_full_ssml=store_full_ssml)
    pipeline.populate_text(assets)
    pipeline.populate_video_text(assets)

    try:
        pipeline.synthesize_audio(assets)
    except Exception as exc:  # pragma: no cover - depends on external TTS
        logging.error(
            "Audio synthesis failed for %s (%s) [%s]: %s",
            record.candidate_name,
            record.constituency,
            pipeline.locale,
            exc,
        )
    try:
        pipeline.render_video(assets)
    except Exception as exc:  # pragma: no cover - depends on runtime env
        logging.error(
            "Video render failed for %s (%s) [%s]: %s",
            record.candidate_name,
            record.constituency,
            pipeline.locale,
            exc,
        )
    else:
        stitched = assets.stitched_video_path
        if stitched:
            logging.info("[%s] Stitched video created at %s", pipeline.locale, stitched)
        else:
            logging.info(
                "[%s] No stitched video produced for %s (%s)",
                pipeline.locale,
                record.candidate_name,
                record.constituency,
            )


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise SystemExit(
            "CSV is missing required columns: " + ", ".join(missing)
        )


def run_batch(csv_path: Path, *, limit: int | None = None, year: str = "2015") -> None:
    configure_output_year(year)
    logging.info("Loading candidate data from %s", csv_path)
    data = pd.read_csv(csv_path)
    _validate_columns(data)

    records = data.to_dict(orient="records")
    if limit is not None:
        records = records[:limit]

    pipelines = {
        "en": NarrationPipeline(locale="en"),
        "hi": NarrationPipeline(locale="hi"),
    }

    for idx, row in enumerate(records, start=1):
        record = _row_to_record(row, year=year)
        if not record.constituency_id or not record.candidate_id:
            logging.warning(
                "Skipping row %d; missing Constituency_ID or Candidate_ID.", idx
            )
            continue

        logging.info(
            "[%d/%d] Processing %s (%s)",
            idx,
            len(records),
            record.candidate_name or "Unknown Candidate",
            record.constituency or "Unknown Constituency",
        )

        _generate_for_locale(record, pipelines["en"], store_full_ssml=False)
        _generate_for_locale(record, pipelines["hi"], store_full_ssml=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate English and Hindi narration assets for every candidate in a CSV.",
    )
    parser.add_argument(
        "csv",
        type=Path,
        help="Path to the candidate CSV file (must include the required columns).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on number of rows to process (useful for smoke tests).",
    )
    parser.add_argument(
        "--year",
        default="2015",
        help="Election year used to route outputs under static/Bihar/winners/<year>/",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR). Default: INFO.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )
    run_batch(args.csv, limit=args.limit, year=args.year)


if __name__ == "__main__":
    main()
