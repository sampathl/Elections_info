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
            lines = [line for line in overlay.text.splitlines() if line.strip()]
            joined = " | ".join(lines) if lines else overlay.text
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
        for segment in pipeline.segment_sequence(assets):
            old_path = segment.audio_path
            if old_path is None:
                continue
            new_path = old_path.with_name(f"{old_path.stem}_en{old_path.suffix}")
            try:
                old_path.rename(new_path)
            except OSError as exc:
                print(f"Failed to rename English audio '{old_path}' -> '{new_path}': {exc}")
            else:
                segment.audio_path = new_path

    hindi_pipeline = NarrationPipeline(locale="hi")
    hindi_assets = hindi_pipeline.build_assets(record)
    hindi_pipeline.populate_ssml(
        hindi_assets,
        wrap_with_speak=True,
        store_full_ssml=True,
    )
    hindi_pipeline.populate_text(hindi_assets)
    hindi_pipeline.populate_video_text(hindi_assets)

    try:
        hindi_pipeline.synthesize_audio(hindi_assets)
    except Exception as exc:  # pragma: no cover - demo script trace
        print(f"Skipping Hindi audio synthesis demo: {exc}")
    else:
        print("\nGenerated Hindi audio files:")
        for segment in hindi_pipeline.segment_sequence(hindi_assets):
            if segment.audio_path:
                print(f"- {segment.key}: {segment.audio_path}")
            else:
                print(f"- {segment.key}: (no audio path)")
        for segment in hindi_pipeline.segment_sequence(hindi_assets):
            old_path = segment.audio_path
            if old_path is None:
                continue
            new_path = old_path.with_name(f"{old_path.stem}_hi{old_path.suffix}")
            try:
                old_path.rename(new_path)
            except OSError as exc:
                print(f"Failed to rename Hindi audio '{old_path}' -> '{new_path}': {exc}")
            else:
                segment.audio_path = new_path

    print("\nHindi segment plain text:")
    for segment in hindi_pipeline.segment_sequence(hindi_assets):
        print(f"- {segment.key}: {segment.text}")

    print("\nHindi video overlay text:")
    for segment in hindi_pipeline.segment_sequence(hindi_assets):
        overlay = segment.overlay_text
        if overlay is None:
            print(f"- {segment.key}: (no overlay text)")
        else:
            lines = [line for line in overlay.text.splitlines() if line.strip()]
            joined = " | ".join(lines) if lines else overlay.text
            print(f"- {segment.key}: {joined}")

    try:
        pipeline.render_video(assets)
    except Exception as exc:  # pragma: no cover - demo script trace
        print(f"\nSkipping video render demo: {exc}")
    else:
        print("\nGenerated video files:")
        for segment in pipeline.segment_sequence(assets):
            if segment.video_path:
                print(f"- {segment.key}: {segment.video_path}")
            else:
                print(f"- {segment.key}: (no video path)")
        if assets.stitched_video_path:
            print(f"Stitched video: {assets.stitched_video_path}")
        else:
            print("No stitched video generated.")

    try:
        hindi_pipeline.render_video(hindi_assets)
    except Exception as exc:  # pragma: no cover - demo script trace
        print(f"\nSkipping Hindi video render demo: {exc}")
    else:
        print("\nGenerated Hindi video files:")
        for segment in hindi_pipeline.segment_sequence(hindi_assets):
            if segment.video_path:
                print(f"- {segment.key}: {segment.video_path}")
            else:
                print(f"- {segment.key}: (no video path)")
        if hindi_assets.stitched_video_path:
            print(f"Stitched Hindi video: {hindi_assets.stitched_video_path}")
        else:
            print("No stitched Hindi video generated.")

    print("\nHindi full SSML text:")
    print(hindi_assets.full_ssml)
    print("\nHindi full plain text:")
    print(hindi_assets.full_text)


if __name__ == "__main__":
    main()
