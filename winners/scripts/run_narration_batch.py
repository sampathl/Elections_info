"""Batch narration generator for English and Hindi videos from a CSV."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed

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
from winners.utils.logging_config import (
    PipelineLoggerAdapter,
    get_pipeline_logger,
    setup_logging,
)

REQUIRED_COLUMNS: Iterable[str] = (
    "constituency_id",
    "candidate_id",
    "constituency",
    "Election_Type",
    "candidate_name",
    "party",
    "criminal_cases",
    "education_details",
    "total_assets",
    "assets_description",
    "total_liabilities",
    "liabilities_description",
    "url",
)


def _sanitize(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _row_to_record(row: Dict[str, object], *, year: str = "") -> CandidateRecord:
    record = CandidateRecord(
        constituency_id=_sanitize(row.get("constituency_id", "")),
        candidate_id=_sanitize(row.get("candidate_id", "")),
        constituency=_sanitize(row.get("constituency", "")),
        election_type=_sanitize(row.get("Election_Type", "")),
        candidate_name=_sanitize(row.get("candidate_name", "")),
        party=_sanitize(row.get("party", "")),
        criminal_cases=_sanitize(row.get("criminal_cases", "")),
        education=_sanitize(row.get("education_details", "")),
        education_details=_sanitize(row.get("education_de", "")),
        age=_sanitize(row.get("age", "")),
        total_assets=_sanitize(row.get("total_assets", "")),
        assets_description=_sanitize(row.get("assets_description", "")),
        total_liabilities=_sanitize(row.get("total_liabilities", "")),
        liabilities_description=_sanitize(row.get("liabilities_description", "")),
        voter_info=_sanitize(row.get("voter_info", "")),
        url=_sanitize(row.get("url", "")),
        election_year=_sanitize(row.get("election_year",""))
    )
    return record


def _generate_for_locale(
    record: CandidateRecord,
    pipeline: NarrationPipeline,
    *,
    store_full_ssml: bool,
    logger: PipelineLoggerAdapter,
) -> CandidateNarrationAssets:
    locale_logger = logger.bind(candidate=record.candidate_id or record.candidate_name or "-", segment="-")
    locale_logger.info(
        "Starting locale pipeline for %s (%s)",
        record.candidate_name or "Unknown Candidate",
        record.constituency or "Unknown Constituency",
    )
    assets = pipeline.build_assets(record)
    pipeline.populate_ssml(assets, wrap_with_speak=True, store_full_ssml=store_full_ssml)
    pipeline.populate_text(assets)
    pipeline.populate_video_text(assets)
    pipeline.synthesize_audio(assets)
    pipeline.render_video(assets)
    locale_logger.info("Locale pipeline complete")
    return assets


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise SystemExit(
            "CSV is missing required columns: " + ", ".join(missing)
        )


def run_batch(
    csv_path: Path,
    *,
    limit: int | None = None,
    year: str = "2015",
    logger: PipelineLoggerAdapter | None = None,
) -> None:
    configure_output_year(year)
    batch_logger = logger or get_pipeline_logger(__name__, component="batch")
    batch_logger.info("Loading candidate data from %s", csv_path)
    data = pd.read_csv(csv_path)
    _validate_columns(data)

    records = data.to_dict(orient="records")
    if limit is not None:
        records = records[:limit]

    pipelines = {
        locale: NarrationPipeline(
            locale=locale,
            logger=batch_logger.bind(component="pipeline", locale=locale),
        )
        for locale in ("en", "hi")
    }

    totals = {locale: {"success": 0, "failure": 0} for locale in pipelines}
    failed_runs: list[tuple[str, str]] = []
    total_records = len(records)

    with ThreadPoolExecutor(max_workers=len(pipelines)) as executor:
        for idx, row in enumerate(records, start=1):
            record = _row_to_record(row, year=year)
            candidate_identifier = record.candidate_id or record.candidate_name or "unknown"
            candidate_logger = batch_logger.bind(candidate=candidate_identifier, locale="-")
            if not record.constituency_id or not record.candidate_id:
                candidate_logger.warning(
                    "Skipping row %d; missing Constituency_ID or Candidate_ID.", idx
                )
                continue

            candidate_logger.info(
                "[%d/%d] Processing %s (%s)",
                idx,
                total_records,
                record.candidate_name or "Unknown Candidate",
                record.constituency or "Unknown Constituency",
            )

            future_to_locale: dict = {}
            for locale, pipeline in pipelines.items():
                locale_logger = candidate_logger.bind(locale=locale)
                future = executor.submit(
                    _generate_for_locale,
                    record,
                    pipeline,
                    store_full_ssml=(locale == "hi"),
                    logger=locale_logger,
                )
                future_to_locale[future] = (locale, locale_logger)

            for future in as_completed(future_to_locale):
                locale, locale_logger = future_to_locale[future]
                try:
                    assets = future.result()
                except Exception:
                    totals[locale]["failure"] += 1
                    locale_logger.exception("Locale pipeline failed")
                    failed_runs.append((candidate_identifier, locale))
                else:
                    totals[locale]["success"] += 1
                    stitched = assets.stitched_video_path
                    if stitched:
                        locale_logger.info("Stitched video created at %s", stitched)
                    else:
                        locale_logger.warning(
                            "No stitched video produced for %s (%s)",
                            record.candidate_name or "Unknown Candidate",
                            record.constituency or "Unknown Constituency",
                        )

            candidate_logger.info("Completed processing")

    for locale, counts in totals.items():
        batch_logger.info(
            "[%s] Success=%d Failure=%d",
            locale,
            counts["success"],
            counts["failure"],
        )

    if failed_runs:
        formatted = ", ".join(f"{candidate}:{locale}" for candidate, locale in failed_runs)
        batch_logger.warning("Failures encountered for: %s", formatted)
    else:
        batch_logger.info("All locale pipelines completed successfully")



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
    parser.add_argument(
        "--file-log-level",
        default="DEBUG",
        help="File handler logging level. Default: DEBUG.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="Directory for batch log files (defaults to <output_root>/logs).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_root = configure_output_year(args.year)
    log_directory = args.log_dir or (output_root / "logs")
    log_path = setup_logging(
        log_directory,
        console_level=args.log_level,
        file_level=args.file_log_level,
    )
    batch_logger = get_pipeline_logger(__name__, component="batch")
    batch_logger.info("Logging configured; file handler at %s", log_path)
    try:
        run_batch(args.csv, limit=args.limit, year=args.year, logger=batch_logger)
    except Exception:
        batch_logger.exception("Narration batch run failed")
        raise


if __name__ == "__main__":
    main()
