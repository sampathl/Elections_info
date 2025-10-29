from __future__ import annotations

from pathlib import Path

import pytest

from winners.entities.candidate_record import CandidateRecord
from winners.entities.narration_assets import CandidateNarrationAssets, SegmentAsset
from winners.video_pipeline.layouts.english import EnglishVideoLayoutStrategy
from winners.video_pipeline.layouts.hindi import HindiVideoLayoutStrategy
from winners.video_pipeline.text_generators import VideoSegmentText


@pytest.fixture
def sample_assets() -> CandidateNarrationAssets:
    record = CandidateRecord(
        constituency_id="243",
        candidate_id="001",
        constituency="Sample Constituency",
        election_type="General Election",
        candidate_name="Sample Candidate",
        party="Example Party",
        criminal_cases="0",
        education="Graduate",
        education_details="B.Sc. 2010",
        age="42",
        total_assets="0",
        assets_description="",
        total_liabilities="0",
        liabilities_description="",
        voter_info="Ward 1, Booth 2",
        url="https://example.com",
    )
    return CandidateNarrationAssets(record=record)


def _touch_backgrounds(directory: Path, *, include_hindi: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    base_filenames = (
        "info",
        "party",
        "board",
        "degree",
        "doctorate",
        "cases",
        "assets",
        "literate",
    )
    for stem in base_filenames:
        (directory / f"{stem}.mp4").touch()
        if include_hindi:
            (directory / f"{stem}_hindi.mp4").touch()


def test_english_layout_background_resolution(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "blue"
    _touch_backgrounds(background_dir)

    strategy = EnglishVideoLayoutStrategy(background_directory=background_dir)

    education_segment = SegmentAsset(
        key="education",
        overlay_text=VideoSegmentText(text="Doctorate holder"),
    )

    background = strategy.background_for_segment(sample_assets, education_segment)
    assert background.name == "doctorate.mp4"

    default_segment = SegmentAsset(
        key="criminal_cases",
        overlay_text=VideoSegmentText(text="Criminal cases: None"),
    )
    default_background = strategy.background_for_segment(sample_assets, default_segment)
    assert default_background.name == "cases.mp4"


def test_english_layout_text_layers(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "blue"
    _touch_backgrounds(background_dir)

    strategy = EnglishVideoLayoutStrategy(background_directory=background_dir)

    segment = SegmentAsset(
        key="name",
        overlay_text=VideoSegmentText(
            text="Sample Candidate\nGeneral Election"
        ),
    )

    specs = strategy.text_layers_for_segment(sample_assets, segment)

    assert len(specs) == 1
    spec = specs[0]
    assert spec.text == "Sample Candidate\nGeneral Election"
    assert spec.font_size > 0
    assert 0 < spec.max_width_ratio <= 1


def test_english_layout_output_filename(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "blue"
    _touch_backgrounds(background_dir)

    strategy = EnglishVideoLayoutStrategy(background_directory=background_dir)

    segment = SegmentAsset(
        key="party",
        overlay_text=VideoSegmentText(text="Example Party"),
    )

    filename = strategy.output_filename_for_segment(sample_assets, segment)
    assert filename.endswith("_party_en.mp4")
    assert "Sample_Candidate" in filename


def test_hindi_layout_background_resolution(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "brown"
    _touch_backgrounds(background_dir, include_hindi=True)

    strategy = HindiVideoLayoutStrategy(background_directory=background_dir)

    education_segment = SegmentAsset(
        key="education",
        overlay_text=VideoSegmentText(text="डॉक्टरेट प्राप्त"),
    )

    background = strategy.background_for_segment(sample_assets, education_segment)
    assert background.name == "doctorate.mp4"

    default_segment = SegmentAsset(
        key="criminal_cases",
        overlay_text=VideoSegmentText(text="कोई आपराधिक मामला नहीं"),
    )
    default_background = strategy.background_for_segment(sample_assets, default_segment)
    assert default_background.name == "cases.mp4"


def test_hindi_layout_text_layers(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "brown"
    _touch_backgrounds(background_dir, include_hindi=True)

    strategy = HindiVideoLayoutStrategy(background_directory=background_dir)

    segment = SegmentAsset(
        key="name",
        overlay_text=VideoSegmentText(text="मनोज मंजिल\nसामान्य चुनाव"),
    )

    specs = strategy.text_layers_for_segment(sample_assets, segment)

    assert len(specs) == 1
    spec = specs[0]
    assert spec.text == "मनोज मंजिल\nसामान्य चुनाव"
    assert spec.font_size == 70
    assert 0 < spec.max_width_ratio <= 1


def test_hindi_layout_output_filename(tmp_path: Path, sample_assets: CandidateNarrationAssets) -> None:
    background_dir = tmp_path / "brown"
    _touch_backgrounds(background_dir, include_hindi=True)

    strategy = HindiVideoLayoutStrategy(background_directory=background_dir)

    segment = SegmentAsset(
        key="party",
        overlay_text=VideoSegmentText(text="भाकपा (माले)"),
    )

    filename = strategy.output_filename_for_segment(sample_assets, segment)
    assert filename.endswith("_party_hi.mp4")
    assert "Sample_Candidate" in filename
