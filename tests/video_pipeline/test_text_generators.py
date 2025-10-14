from __future__ import annotations

import pytest

from src.audio_pipeline.pipelines.narration import NarrationPipeline
from src.entities.candidate_record import CandidateRecord
from src.video_pipeline.text_generators import VideoSegmentText, VideoTextFactory
from src.video_pipeline.text_generators.english import EnglishVideoTextFormatter
from src.video_pipeline.text_generators.hindi import HindiVideoTextFormatter
from src.video_pipeline.text_generators import hindi as hindi_module


def _sample_record() -> CandidateRecord:
    return CandidateRecord(
        constituency="AGIAON (SC)",
        election_type="General Election",
        candidate_name="Manoj Manzil",
        party="CPI(ML)(L)",
        criminal_cases="2",
        education="Graduate",
        education_details="B.A. from H.D. Jain College, Ara in 2015",
        age="36",
        total_assets="316500",
        assets_description="3 Lakh",
        total_liabilities="10000",
        liabilities_description="10 Thousand",
        voter_info="196-Tarari constituency, Serial 619, Part 140",
        url="https://www.myneta.info/bihar2020/candidate.php?candidate_id=9784",
    )


def test_factory_returns_english_formatter() -> None:
    factory = VideoTextFactory()
    formatter = factory.create("en")

    assert isinstance(formatter, EnglishVideoTextFormatter)
    assert formatter.locale == "en"


def test_english_formatter_segments_expected_text() -> None:
    formatter = EnglishVideoTextFormatter()
    segments = formatter.segment_texts(_sample_record())

    assert segments["name"].primary == "Manoj Manzil"
    assert segments["name"].secondary == "General Election"

    assert segments["party"].primary == "CPI(ML)(L)"
    assert segments["party"].secondary == "Political party"

    assert segments["constituency"].callouts == (
        "196-Tarari constituency, Serial 619, Part 140",
    )

    assert segments["assets"].primary == "Assets: 3 lakh"
    assert segments["liabilities"].primary == "Liabilities: 10 thousand"
    assert segments["criminal_cases"].primary == "Criminal cases: 2"


def test_segment_text_lines_compose_all_fields() -> None:
    segment = VideoSegmentText(
        primary="Headline",
        secondary="Detail",
        callouts=("Extra",),
    )

    assert segment.lines() == ("Headline", "Detail", "Extra")


def test_pipeline_populate_video_text_updates_assets() -> None:
    pipeline = NarrationPipeline(locale="en")
    assets = pipeline.build_assets(_sample_record())

    pipeline.populate_video_text(assets)

    name_segment = assets.segments["name"]
    assert name_segment.overlay_text is not None
    assert name_segment.overlay_text.primary == "Manoj Manzil"


@pytest.fixture
def stub_transliteration(monkeypatch: pytest.MonkeyPatch):
    def _fake_transliteration(text: str, **_: object) -> str:
        return f"देवनागरी:{text}"

    monkeypatch.setattr(
        hindi_module, "generate_native_transliteration", _fake_transliteration
    )
    return _fake_transliteration


def test_factory_returns_hindi_formatter(stub_transliteration) -> None:
    factory = VideoTextFactory()
    formatter = factory.create("hi")

    assert isinstance(formatter, HindiVideoTextFormatter)
    assert formatter.locale == "hi"


def test_hindi_formatter_segments_expected_text(stub_transliteration) -> None:
    formatter = HindiVideoTextFormatter()
    segments = formatter.segment_texts(_sample_record())

    assert segments["age"].primary == "आयु: ३६"
    assert segments["party"].secondary == "राजनीतिक दल"
    assert segments["party"].primary == "देवनागरी:CPI(ML)(L)"
    assert segments["constituency"].primary == "देवनागरी:AGIAON (SC)"
    assert segments["constituency"].callouts == (
        "देवनागरी:196-Tarari constituency, Serial 619, Part 140",
    )
    assert segments["name"].primary == "देवनागरी:Manoj Manzil"
    assert segments["name"].secondary == "देवनागरी:General Election"
    assert segments["education"].secondary == "देवनागरी:B.A. from H.D. Jain College, Ara in 2015"
    assert segments["assets"].primary == "संपत्ति: ३ लाख"
    assert segments["liabilities"].primary == "ऋण: १० हज़ार"
    assert segments["criminal_cases"].primary == "आपराधिक मामले: २"


def test_pipeline_populate_video_text_hindi_updates_assets(stub_transliteration) -> None:
    pipeline = NarrationPipeline(locale="hi")
    assets = pipeline.build_assets(_sample_record())

    pipeline.populate_video_text(assets)

    assets_segment = assets.segments["assets"]
    assert assets_segment.overlay_text is not None
    assert assets_segment.overlay_text.primary == "संपत्ति: ३ लाख"
    name_segment = assets.segments["name"]
    assert name_segment.overlay_text is not None
    assert name_segment.overlay_text.primary == "देवनागरी:Manoj Manzil"
