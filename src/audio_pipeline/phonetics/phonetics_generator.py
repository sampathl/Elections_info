"""Utilities for generating SSML or IPA phoneme strings for Romanised names."""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

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
    native: Optional[str] = None
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

    def _transliterate_word(self, word: str) -> str:
        xlit_map = self._xlit_engine.translit_word(word, topk=1)
        native_options = xlit_map.get(self.native_lang_code)
        native_word = native_options[0] if native_options else word
        return native_word

    def _ipa_from_native(self, native_word: str) -> str:
        return self._epi.transliterate(native_word)

    def _transcribe_core(self, word: str) -> Tuple[str, str]:
        native_word = self._transliterate_word(word)
        ipa_value = self._ipa_from_native(native_word)
        return native_word, ipa_value

    def phonemes(self, text: str) -> List[Phoneme]:
        tokens = []
        for token in self._tokenise(text):
            if re.match(r"[.,!?;]", token):
                tokens.append(
                    Phoneme(word=token, ipa=token, native=token, is_punctuation=True)
                )
                continue

            if len(token) <= 1:
                tokens.append(Phoneme(word=token, ipa=token, native=token))
                continue

            try:
                native_word, ipa_value = self._transcribe_core(token)
                tokens.append(Phoneme(word=token, ipa=ipa_value, native=native_word))
            except Exception as exc:
                logger.warning("Falling back to plain text for '%s': %s", token, exc)
                tokens.append(Phoneme(word=token, ipa=token, native=token))

        return tokens

    def _render_ssml(
        self,
        text: str,
        *,
        wrap_with_speak: bool,
        surface_fn: Callable[[Phoneme], str],
    ) -> str:
        fragments: List[str] = []
        for phoneme in self.phonemes(text):
            if phoneme.is_punctuation:
                fragments.append(phoneme.word)
            else:
                surface_text = surface_fn(phoneme)
                fragments.append(
                    f'<phoneme alphabet="ipa" ph="{phoneme.ipa}">{surface_text}</phoneme>'
                )

        ssml_body = " ".join(fragment for fragment in fragments if fragment)
        if wrap_with_speak:
            return f"<speak>{ssml_body}</speak>"
        return ssml_body

    def to_ssml(self, text: str, *, wrap_with_speak: bool = False) -> str:
        return self._render_ssml(
            text,
            wrap_with_speak=wrap_with_speak,
            surface_fn=lambda phoneme: phoneme.word,
        )

    def to_ssml_native(self, text: str, *, wrap_with_speak: bool = False) -> str:
        """Return SSML with native-script surface text inside each phoneme tag."""
        return self._render_ssml(
            text,
            wrap_with_speak=wrap_with_speak,
            surface_fn=lambda phoneme: phoneme.native
            if phoneme.native is not None
            else phoneme.word,
        )

    def to_native_text(self, text: str, *, joiner: str = " ") -> str:
        pieces: List[str] = []
        for phoneme in self.phonemes(text):
            pieces.append(phoneme.native if phoneme.native is not None else phoneme.word)
        return joiner.join(pieces).strip()

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


def generate_ssml_phonetics_native(
    text: str,
    *,
    wrap_with_speak: bool = False,
    transcriber: Optional[PhoneticTranscriber] = None,
) -> str:
    """Return SSML with native-script surface text (optionally wrapped with <speak>)."""

    engine = transcriber or _get_default_transcriber()
    return engine.to_ssml_native(text, wrap_with_speak=wrap_with_speak)


def generate_native_transliteration(
    text: str,
    *,
    joiner: str = " ",
    transcriber: Optional[PhoneticTranscriber] = None,
) -> str:
    """Return the native-script transliteration for the supplied text."""

    engine = transcriber or _get_default_transcriber()
    return engine.to_native_text(text, joiner=joiner)


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
    "generate_ssml_phonetics_native",
    "generate_native_transliteration",
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
        "--native",
        action="store_true",
        help="Output native-script transliteration instead of SSML.",
    )
    parser.add_argument(
        "--ssml-native",
        action="store_true",
        help="Output SSML with native-script surface text instead of English.",
    )
    parser.add_argument(
        "--wrap",
        action="store_true",
        help="Wrap SSML output with <speak> tags.",
    )
    args = parser.parse_args()

    selected_modes = sum(
        bool(flag) for flag in (args.ipa, args.native, args.ssml_native)
    )
    if selected_modes > 1:
        parser.error("Choose at most one of --ipa, --native, or --ssml-native.")

    if args.native:
        print(generate_native_transliteration(args.text))
    elif args.ipa:
        print(generate_phoneme_string(args.text))
    elif args.ssml_native:
        print(generate_ssml_phonetics_native(args.text, wrap_with_speak=args.wrap))
    else:
        print(generate_ssml_phonetics(args.text, wrap_with_speak=args.wrap))

    print(generate_native_transliteration(args.text))
    print(generate_phoneme_string(args.text))
    print(generate_ssml_phonetics(args.text, wrap_with_speak=args.wrap))
    print(generate_ssml_phonetics_native(args.text, wrap_with_speak=args.wrap))
