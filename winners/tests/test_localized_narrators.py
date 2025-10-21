"""Smoke tests for English and Hindi localized narrators.

Run with ``python tests/test_localized_narrators.py``. The script prints
generated SSML for both locales; if the transliteration dependencies are
missing, the tests are skipped with a message.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PARENT = PROJECT_ROOT.parent
for path in (PROJECT_PARENT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


try:
    from winners.entities.candidate_record import CandidateRecord
    from winners.audio_pipeline.ssml_generators.factory import CandidateNarratorFactory
except ModuleNotFoundError as exc:  # e.g. optional deps like `inflect` missing
    CandidateRecord = None  # type: ignore[assignment]
    CandidateNarratorFactory = None  # type: ignore[assignment]
    MISSING_DEPENDENCY = str(exc)
else:
    MISSING_DEPENDENCY = None

try:
    import pytest
except ModuleNotFoundError:  # pragma: no cover - running as script
    pytest = None  # type: ignore[assignment]
else:
    if MISSING_DEPENDENCY is not None:
        pytestmark = pytest.mark.skip(
            reason=f"Skipping narrator smoke tests (missing dependency: {MISSING_DEPENDENCY})"
        )


def _sample_entity() -> CandidateRecord:
    return CandidateRecord(
        constituency_id="243",
        candidate_id="001",
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


def test_english_narrator() -> None:
    factory = CandidateNarratorFactory()
    narrator = factory.create("en")
    entity = _sample_entity()

    segments = narrator.ssml_segments(entity)
    assert segments["name"], "Name segment should not be empty"
    print("English segments:", segments)
    ssml = narrator.ssml_text(entity)
    assert ssml.startswith("<speak>") and "</speak>" in ssml
    print("English SSML:", ssml)


def test_hindi_narrator() -> None:
    factory = CandidateNarratorFactory()
    narrator = factory.create("hi")
    entity = _sample_entity()

    segments = narrator.ssml_segments(entity)
    assert segments["name"], "Name segment should not be empty"
    print("Hindi segments:", segments)

    ssml = narrator.ssml_text(entity)
    assert ssml.startswith("<speak>") and "</speak>" in ssml
    print("Hindi SSML:", ssml)


def main() -> None:
    if MISSING_DEPENDENCY is not None:
        print(f"SKIPPED narrator tests: {MISSING_DEPENDENCY}")
        return

    try:
        test_english_narrator()
        test_hindi_narrator()
        print("All narrator smoke tests passed.")
    except RuntimeError as exc:
        print(f"SKIPPED narrator tests: {exc}")


if __name__ == "__main__":
    main()
