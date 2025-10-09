"""Shim module for backward compatibility.

The localized election narration components now live under
``data_operators.localized_narration``. This module re-exports the public
interfaces and delegates the demo CLI entry-point so existing imports continue
to work during the transition.
"""

from __future__ import annotations

from data_operators.localized_narration import (
    CandidateNarrator,
    CandidateNarratorFactory,
    EnglishNarrationFormatter,
    HindiNarrationFormatter,
    LocaleFormatter,
    LocalizedNarrator,
    MoneyAmount,
    MoneyParser,
)

__all__ = [
    "CandidateNarrator",
    "CandidateNarratorFactory",
    "EnglishNarrationFormatter",
    "HindiNarrationFormatter",
    "LocaleFormatter",
    "LocalizedNarrator",
    "MoneyAmount",
    "MoneyParser",
]


def main(argv: list[str] | None = None) -> int:
    from data_operators.localized_narration.cli import main as _cli_main

    return _cli_main(argv)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    raise SystemExit(main())

