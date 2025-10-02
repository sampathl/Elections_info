"""Utility helpers for translating English nouns to Hindi using Google Translate."""

from __future__ import annotations

from typing import Iterable, List, Dict, Any

try:
    from googletrans import Translator
except ImportError as exc:  # pragma: no cover - import guard
    raise ImportError(
        "googletrans is required for translation.py. Install with 'pip install googletrans==4.0.0-rc1'."
    ) from exc


def translate_nouns_to_hindi(
    nouns: Iterable[str], include_pronunciation: bool = True
) -> List[Dict[str, Any]]:
    """Translate a list of English nouns to Hindi using Google Translate.

    Args:
        nouns: Iterable of English nouns to translate.
        include_pronunciation: Whether to include romanized pronunciation (if available).

    Returns:
        A list of dictionaries with ``english`` and ``hindi`` keys. ``pronunciation`` is
        added when ``include_pronunciation`` is True. Items that are empty or only whitespace
        are ignored.
    """

    translator = Translator()

    clean_nouns = [noun.strip() for noun in nouns if noun and noun.strip()]
    if not clean_nouns:
        return []

    translations = translator.translate(clean_nouns, dest="hi", src="en")

    results: List[Dict[str, Any]] = []
    for original, translation in zip(clean_nouns, translations):
        entry: Dict[str, Any] = {
            "english": original,
            "hindi": translation.text,
        }

        if include_pronunciation:
            entry["pronunciation"] = translation.pronunciation

        results.append(entry)

    return results


def _demo() -> None:
    """Quick demo when running this module directly."""

    sample_nouns = ["river", "mountain", "festival", "market"]
    translations = translate_nouns_to_hindi(sample_nouns)
    for item in translations:
        english = item["english"]
        hindi = item["hindi"]
        pronunciation = item.get("pronunciation")
        if pronunciation:
            print(f"{english} -> {hindi} ({pronunciation})")
        else:
            print(f"{english} -> {hindi}")


if __name__ == "__main__":
    _demo()
