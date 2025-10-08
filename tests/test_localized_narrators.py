"""Smoke tests for English and Hindi localized narrators.

Run with ``python tests/test_localized_narrators.py``. The script prints
generated SSML for both locales; if the transliteration dependencies are
missing, the tests are skipped with a message.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from data_operators.election_entities import CandidateRecord
    from data_operators.localized_narration import CandidateNarratorFactory
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency missing
    MISSING_DEPENDENCY = exc
else:
    MISSING_DEPENDENCY = None


def _sample_entity() -> CandidateRecord:
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


def test_english_narrator() -> None:
    factory = CandidateNarratorFactory()
    narrator = factory.create("en")
    entity = _sample_entity()

    segments = narrator.ssml_segments(entity)
    assert segments["name"], "Name segment should not be empty"

    ssml = narrator.ssml_text(entity)
    assert ssml.startswith("<speak>") and "</speak>" in ssml
    print("English SSML:", ssml)


def test_hindi_narrator() -> None:
    factory = CandidateNarratorFactory()
    narrator = factory.create("hi")
    entity = _sample_entity()

    segments = narrator.ssml_segments(entity)
    assert segments["name"], "Name segment should not be empty"

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
