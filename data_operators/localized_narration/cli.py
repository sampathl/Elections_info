"""Convenience CLI for generating localized election narration."""

from __future__ import annotations

import argparse
import json

from .factory import CandidateNarratorFactory

try:  # pragma: no cover - support package-relative and standalone execution
    from ..election_entities import CandidateRecord
except ImportError:  # pragma: no cover
    from election_entities import CandidateRecord  # type: ignore

__all__ = ["main"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate localized election narration as SSML."
    )
    parser.add_argument("locale", choices=("en", "hi"), help="Locale to narrate in.")
    parser.add_argument(
        "--segments",
        action="store_true",
        help="Output JSON with individual SSML segments.",
    )
    return parser


def sample_record() -> CandidateRecord:
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    factory = CandidateNarratorFactory()
    narrator = factory.create(args.locale)
    entity = sample_record()

    if args.segments:
        segments = narrator.ssml_segments(entity)
        print(json.dumps(segments, indent=2, ensure_ascii=False))
    else:
        print(narrator.ssml_text(entity))

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

