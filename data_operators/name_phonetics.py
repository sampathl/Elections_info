"""Utilities for generating SSML or IPA phoneme strings for Romanised names."""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import torch

try:
    from ai4bharat.transliteration import XlitEngine
    import epitran
except ImportError as exc:  # pragma: no cover - depends on optional packages
    raise RuntimeError(
        "ai4bharat.transliteration and epitran are required for name_phonetics"
    ) from exc


torch.serialization.add_safe_globals([argparse.Namespace])

logger = logging.getLogger(__name__)


# Basic ISO-639-1 to ISO-639-3 mapping used by Epitran.
_ISO6393 = {
    "bn": "ben",
    "gu": "guj",
    "hi": "hin",
    "kn": "kan",
    "ml": "mal",
    "mr": "mar",
    "or": "ori",
    "pa": "pan",
    "ta": "tam",
    "te": "tel",
}


@dataclass(frozen=True)
class Phoneme:
    word: str
    ipa: str
    is_punctuation: bool = False


def _resolve_epitran_lang(native_lang_code: str) -> str:
    if len(native_lang_code) == 3:
        return native_lang_code
    return _ISO6393.get(native_lang_code, native_lang_code)


class PhoneticTranscriber:
    """Transcribes Romanised names to IPA and SSML fragments."""

    def __init__(
        self,
        native_lang_code: str = "hi",
        native_script: str = "Deva",
        *,
        xlit_engine: Optional[XlitEngine] = None,
        epi: Optional[epitran.Epitran] = None,
    ) -> None:
        epi_lang_code = _resolve_epitran_lang(native_lang_code)

        try:
            self._xlit_engine = xlit_engine or XlitEngine(
                native_lang_code, src_script_type="roman"
            )
        except Exception as exc:  # pragma: no cover - library initialisation
            raise RuntimeError(
                f"Failed to initialise XlitEngine for '{native_lang_code}'."
            ) from exc

        try:
            self._epi = epi or epitran.Epitran(f"{epi_lang_code}-{native_script}")
        except Exception as exc:  # pragma: no cover - library initialisation
            raise RuntimeError(
                f"Failed to initialise Epitran for '{epi_lang_code}-{native_script}'."
            ) from exc

        self.native_lang_code = native_lang_code

    @staticmethod
    def _tokenise(text: str) -> List[str]:
        return re.findall(r"[\w']+|[.,!?;]", text)

    def _transcribe_core(self, word: str) -> str:
        xlit_map = self._xlit_engine.translit_word(word, topk=1)
        native_options = xlit_map.get(self.native_lang_code)
        native_word = native_options[0] if native_options else word
        return self._epi.transliterate(native_word)

    def phonemes(self, text: str) -> List[Phoneme]:
        tokens = []
        for token in self._tokenise(text):
            if re.match(r"[.,!?;]", token):
                tokens.append(Phoneme(word=token, ipa=token, is_punctuation=True))
                continue

            if len(token) <= 1:
                tokens.append(Phoneme(word=token, ipa=token))
                continue

            try:
                ipa_value = self._transcribe_core(token)
                tokens.append(Phoneme(word=token, ipa=ipa_value))
            except Exception as exc:
                logger.warning("Falling back to plain text for '%s': %s", token, exc)
                tokens.append(Phoneme(word=token, ipa=token))

        return tokens

    def to_ssml(self, text: str, *, wrap_with_speak: bool = False) -> str:
        fragments: List[str] = []
        for phoneme in self.phonemes(text):
            if phoneme.is_punctuation:
                fragments.append(phoneme.word)
            else:
                fragments.append(
                    f'<phoneme alphabet="ipa" ph="{phoneme.ipa}">{phoneme.word}</phoneme>'
                )

        ssml_body = " ".join(fragment for fragment in fragments if fragment)
        if wrap_with_speak:
            return f"<speak>{ssml_body}</speak>"
        return ssml_body

    def to_ipa_string(self, text: str, *, joiner: str = " ") -> str:
        pieces: List[str] = []
        for phoneme in self.phonemes(text):
            pieces.append(phoneme.ipa)
        return joiner.join(pieces).strip()


_DEFAULT_TRANSCRIBER: Optional[PhoneticTranscriber] = None


def _get_default_transcriber() -> PhoneticTranscriber:
    global _DEFAULT_TRANSCRIBER
    if _DEFAULT_TRANSCRIBER is None:
        _DEFAULT_TRANSCRIBER = PhoneticTranscriber()
    return _DEFAULT_TRANSCRIBER


def generate_ssml_phonetics(
    text: str,
    *,
    wrap_with_speak: bool = False,
    transcriber: Optional[PhoneticTranscriber] = None,
) -> str:
    """Return an SSML fragment (optionally wrapped with <speak>) for the input."""

    engine = transcriber or _get_default_transcriber()
    return engine.to_ssml(text, wrap_with_speak=wrap_with_speak)


def generate_phoneme_string(
    text: str,
    *,
    joiner: str = " ",
    transcriber: Optional[PhoneticTranscriber] = None,
) -> str:
    """Return only the IPA phoneme string for the supplied text."""

    engine = transcriber or _get_default_transcriber()
    return engine.to_ipa_string(text, joiner=joiner)


__all__ = [
    "PhoneticTranscriber",
    "Phoneme",
    "generate_ssml_phonetics",
    "generate_phoneme_string",
]


if __name__ == "__main__":  # pragma: no cover - convenience CLI
    import argparse as _argparse

    parser = _argparse.ArgumentParser(
        description="Generate SSML or IPA phonemes for Romanised names."
    )
    parser.add_argument("text", help="Name or text to transcribe")
    parser.add_argument(
        "--ipa",
        action="store_true",
        help="Output IPA phoneme string instead of SSML.",
    )
    parser.add_argument(
        "--wrap",
        action="store_true",
        help="Wrap SSML output with <speak> tags.",
    )
    args = parser.parse_args()

    if args.ipa:
        print(generate_phoneme_string(args.text))
    else:
        print(generate_ssml_phonetics(args.text, wrap_with_speak=args.wrap))
