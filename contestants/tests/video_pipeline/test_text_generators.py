from __future__ import annotations

import pytest

from contestants.audio_pipeline.pipelines.narration import NarrationPipeline
from contestants.entities.candidate_record import CandidateRecord
from contestants.video_pipeline.text_generators import VideoSegmentText, VideoTextFactory
from contestants.video_pipeline.text_generators.english import EnglishVideoTextFormatter
from contestants.video_pipeline.text_generators.hindi import HindiVideoTextFormatter
from contestants.video_pipeline.text_generators import hindi as hindi_module


def _sample_record() -> CandidateRecord:
    return CandidateRecord(
        constituency_id="243",
        candidate_id="001",
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

    assert segments["name"].text == "Manoj Manzil\nGeneral Election"

    assert segments["party"].text == "CPI(ML)(L)\nPolitical party"

    assert segments["constituency"].text == (
        "AGIAON (SC)\nConstituency\n196-Tarari constituency, Serial 619, Part 140"
    )

    assert segments["assets"].text == "316,500"
    assert segments["liabilities"].text == "10,000"
    assert segments["criminal_cases"].text == "Criminal cases: 2"


def test_video_segment_text_preserves_text() -> None:
    segment = VideoSegmentText(text="Headline\nDetail\nExtra")
    assert segment.text == "Headline\nDetail\nExtra"


def test_pipeline_populate_video_text_updates_assets() -> None:
    pipeline = NarrationPipeline(locale="en")
    assets = pipeline.build_assets(_sample_record())

    pipeline.populate_video_text(assets)

    name_segment = assets.segments["name"]
    assert name_segment.overlay_text is not None
    assert name_segment.overlay_text.text.startswith("Manoj Manzil")


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

    assert segments["age"].text == "३६"
    assert segments["party"].text == "देवनागरी:CPI(ML)(L)\nराजनीतिक दल"
    assert segments["constituency"].text == (
        "देवनागरी:AGIAON (SC)\nनिर्वाचन क्षेत्र\nदेवनागरी:196-Tarari constituency, Serial 619, Part 140"
    )
    assert segments["name"].text == "देवनागरी:Manoj Manzil\nदेवनागरी:General Election"
    assert segments["education"].text == (
        "स्नातक शिक्षा प्राप्त है\nदेवनागरी:B.A. from H.D. Jain College, Ara in 2015"
    )
    assert segments["assets"].text == "३,१६,५००"
    assert segments["liabilities"].text == "१०,०००"
    assert segments["criminal_cases"].text == "आपराधिक मामले: २"


def test_pipeline_populate_video_text_hindi_updates_assets(stub_transliteration) -> None:
    pipeline = NarrationPipeline(locale="hi")
    assets = pipeline.build_assets(_sample_record())

    pipeline.populate_video_text(assets)

    assets_segment = assets.segments["assets"]
    assert assets_segment.overlay_text is not None
    assert assets_segment.overlay_text.text == "३,१६,५००"
    name_segment = assets.segments["name"]
    assert name_segment.overlay_text is not None
    assert name_segment.overlay_text.text.startswith("देवनागरी:Manoj Manzil")
