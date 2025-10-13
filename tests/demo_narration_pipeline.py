"""Demonstration script for the narration pipeline SSML stage."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.entities.candidate_record import CandidateRecord
    from src.audio_pipeline.pipelines.narration import NarrationPipeline
except ModuleNotFoundError as exc:
    print(f"SKIPPED narration demo: {exc}")
    raise SystemExit(0)


def _sample_record() -> CandidateRecord:
    """Return a sample candidate record used in smoke tests."""

    return CandidateRecord(
        constituency="AGIAON (SC)",
        election_type="General",
        candidate_name="Manoj Manzil",
        party="CPI(ML)(L)",
        criminal_cases="30",
        education="Graduate",
        education_details="B.A. from H.D. Jain College, Ara in 2015",
        age="36",
        total_assets="316500",
        assets_description="3 Lakh",
        total_liabilities="10000",
        liabilities_description="10 Thousand",
        voter_info="196-Tarari (Bihar) constituency, at Serial no 619 in Part no 140",
        url="https://www.myneta.info/bihar2020/candidate.php?candidate_id=9784",
    )


def main() -> None:
    locale = "en"
    pipeline = NarrationPipeline(locale=locale)
    record = _sample_record()
    assets = pipeline.build_assets(record)
    pipeline.populate_ssml(assets, wrap_with_speak=True)

    print(f"Narration SSML segments for locale '{locale}':")
    for segment in pipeline.segment_sequence(assets):
        print(f"- {segment.key}: {segment.ssml}")


if __name__ == "__main__":
    main()
