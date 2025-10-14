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
    pipeline.populate_video_text(assets)

    print(f"Narration SSML segments for locale '{locale}':")
    for segment in pipeline.segment_sequence(assets):
        print(f"- {segment.key}: {segment.ssml}")

    print("\nEnglish video overlay text:")
    for segment in pipeline.segment_sequence(assets):
        overlay = segment.overlay_text
        if overlay is None:
            print(f"- {segment.key}: (no overlay text)")
        else:
            joined = " | ".join(overlay.lines())
            print(f"- {segment.key}: {joined}")

    try:
        pipeline.synthesize_audio(assets)
    except Exception as exc:  # pragma: no cover - demo script trace
        print(f"Skipping audio synthesis demo: {exc}")
    else:
        print("\nGenerated audio files:")
        for segment in pipeline.segment_sequence(assets):
            if segment.audio_path:
                print(f"- {segment.key}: {segment.audio_path}")
            else:
                print(f"- {segment.key}: (no audio path)")

    hindi_pipeline = NarrationPipeline(locale="hi")
    hindi_assets = hindi_pipeline.build_assets(record)
    hindi_pipeline.populate_ssml(
        hindi_assets,
        wrap_with_speak=True,
        store_full_ssml=True,
    )
    hindi_pipeline.populate_text(hindi_assets)
    hindi_pipeline.populate_video_text(hindi_assets)

    
    print("\nHindi segment plain text:")
    for segment in hindi_pipeline.segment_sequence(hindi_assets):
        print(f"- {segment.key}: {segment.text}")
    print("\nHindi video overlay text:")
    for segment in hindi_pipeline.segment_sequence(hindi_assets):
        overlay = segment.overlay_text
        if overlay is None:
            print(f"- {segment.key}: (no overlay text)")
        else:
            joined = " | ".join(overlay.lines())
            print(f"- {segment.key}: {joined}")

    print("\nHindi full SSML text:")
    print(hindi_assets.full_ssml)
    print("\nHindi full plain text:")
    print(hindi_assets.full_text)


if __name__ == "__main__":
    main()
