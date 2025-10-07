"""Phonetics utilities with optional dependency loading and locale-aware caching.

This module introduces a more flexible design around phonetic transcription:

* Optional dependencies (`ai4bharat.transliteration`, `epitran`) are loaded lazily
  so the package can be imported without the heavy runtime stack.
* A registry caches transcribers per (language, script, token pattern) tuple,
  avoiding repeated initialisation overheads for frequently used locales.
* Tokenisation can be customised per transcriber, enabling better handling of
  hyphenated names, numerals, or locale-specific punctuation.
* Callers can supply failure callbacks to react to transliteration issues
  instead of relying purely on log messages.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Pattern, Protocol

logger = logging.getLogger(__name__)


class TransliterationUnavailable(RuntimeError):
    """Raised when optional transliteration dependencies are missing."""


def _import_transliteration_dependencies():
    try:  # pragma: no cover - exercised only when optional deps exist
        from ai4bharat.transliteration import XlitEngine  # type: ignore
        import epitran  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on optional packages
        raise TransliterationUnavailable(
            "Install 'ai4bharat-transliteration' and 'epitran' to enable phonetics"
        ) from exc

    return XlitEngine, epitran


@lru_cache(maxsize=1)
def _load_transliteration_dependencies():
    return _import_transliteration_dependencies()


def _resolve_epitran_lang(native_lang_code: str) -> str:
    mapping = {
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
    if len(native_lang_code) == 3:
        return native_lang_code
    return mapping.get(native_lang_code, native_lang_code)


class PhoneticsProvider(Protocol):
    """Common interface for phonetic helpers used across the code base."""

    def to_ssml(self, text: str, *, wrap_with_speak: bool = False) -> str:
        ...

    def to_ipa_string(self, text: str, *, joiner: str = " ") -> str:
        ...


class PhonemeFallback(Protocol):
    """Callback invoked when the transliteration pipeline fails for a token."""

    def __call__(self, token: str, exc: Exception) -> None:
        ...


@dataclass(frozen=True)
class Phoneme:
    word: str
    ipa: str
    is_punctuation: bool = False


class RomanisedPhoneticTranscriber(PhoneticsProvider):
    """Transcribes Romanised tokens into IPA/SSML using ai4bharat + Epitran."""

    def __init__(
        self,
        native_lang_code: str = "hi",
        native_script: str = "Deva",
        *,
        token_pattern: str = r"[\w\-’']+|[^\w\s]",
        on_fallback: Optional[PhonemeFallback] = None,
    ) -> None:
        XlitEngine, epitran = _load_transliteration_dependencies()

        self.native_lang_code = native_lang_code
        epi_lang_code = _resolve_epitran_lang(native_lang_code)
        self._token_regex: Pattern[str] = re.compile(token_pattern)
        self._on_fallback = on_fallback

        try:  # pragma: no cover - depends on optional packages at runtime
            self._xlit_engine = XlitEngine(native_lang_code, src_script_type="roman")
        except Exception as exc:
            raise TransliterationUnavailable(
                f"Failed to initialise XlitEngine for '{native_lang_code}'"
            ) from exc

        try:  # pragma: no cover - depends on optional packages at runtime
            self._epi = epitran.Epitran(f"{epi_lang_code}-{native_script}")
        except Exception as exc:
            raise TransliterationUnavailable(
                f"Failed to initialise Epitran for '{epi_lang_code}-{native_script}'"
            ) from exc

    def _tokenise(self, text: str) -> Iterable[str]:
        return self._token_regex.findall(text)

    def _transcribe_core(self, token: str) -> str:
        xlit_map = self._xlit_engine.translit_word(token, topk=1)
        native_options = xlit_map.get(self.native_lang_code)
        native_word = native_options[0] if native_options else token
        return self._epi.transliterate(native_word)

    def _handle_failure(self, token: str, exc: Exception) -> None:
        if self._on_fallback:
            self._on_fallback(token, exc)
        else:
            logger.warning("Falling back to plain token '%s': %s", token, exc)

    def phonemes(self, text: str) -> List[Phoneme]:
        tokens: List[Phoneme] = []
        for token in self._tokenise(text):
            if re.fullmatch(r"[^\w\s]", token):
                tokens.append(Phoneme(word=token, ipa=token, is_punctuation=True))
                continue

            if len(token) <= 1:
                tokens.append(Phoneme(word=token, ipa=token))
                continue

            try:
                ipa_value = self._transcribe_core(token)
                tokens.append(Phoneme(word=token, ipa=ipa_value))
            except Exception as exc:  # pragma: no cover - depends on runtime
                self._handle_failure(token, exc)
                tokens.append(Phoneme(word=token, ipa=token))

        return tokens

    def to_ssml(self, text: str, *, wrap_with_speak: bool = False) -> str:
        fragments: List[str] = []
        for phoneme in self.phonemes(text):
            if phoneme.is_punctuation:
                fragments.append(phoneme.word)
                continue

            fragments.append(
                f'<phoneme alphabet="ipa" ph="{phoneme.ipa}">{phoneme.word}</phoneme>'
            )

        body = " ".join(fragment for fragment in fragments if fragment)
        if wrap_with_speak:
            return f"<speak>{body}</speak>"
        return body

    def to_ipa_string(self, text: str, *, joiner: str = " ") -> str:
        pieces = [phoneme.ipa for phoneme in self.phonemes(text)]
        return joiner.join(pieces).strip()


@dataclass(frozen=True)
class TranscriberKey:
    lang: str
    script: str
    token_pattern: str = r"[\w\-’']+|[^\w\s]"


class TranscriberRegistry:
    """Cache of phonetic transcribers keyed by locale/script configuration."""

    def __init__(self) -> None:
        self._cache: Dict[TranscriberKey, RomanisedPhoneticTranscriber] = {}
        self._lock = threading.Lock()

    def get(
        self,
        lang: str = "hi",
        script: str = "Deva",
        *,
        token_pattern: str = r"[\w\-’']+|[^\w\s]",
        on_fallback: Optional[PhonemeFallback] = None,
    ) -> RomanisedPhoneticTranscriber:
        key = TranscriberKey(lang, script, token_pattern)

        with self._lock:
            transcriber = self._cache.get(key)
            if transcriber is None:
                transcriber = RomanisedPhoneticTranscriber(
                    lang,
                    script,
                    token_pattern=token_pattern,
                    on_fallback=on_fallback,
                )
                self._cache[key] = transcriber

        return transcriber


_GLOBAL_REGISTRY = TranscriberRegistry()


def get_transcriber(
    lang: str = "hi",
    script: str = "Deva",
    *,
    token_pattern: str = r"[\w\-’']+|[^\w\s]",
    on_fallback: Optional[PhonemeFallback] = None,
) -> RomanisedPhoneticTranscriber:
    """Return a cached transcriber for the requested locale configuration."""

    return _GLOBAL_REGISTRY.get(
        lang,
        script,
        token_pattern=token_pattern,
        on_fallback=on_fallback,
    )


def generate_ssml_phonetics(
    text: str,
    *,
    lang: str = "hi",
    script: str = "Deva",
    wrap_with_speak: bool = False,
    token_pattern: str = r"[\w\-’']+|[^\w\s]",
) -> str:
    """Convenience helper mirroring the legacy interface with caching built in."""

    engine = get_transcriber(lang, script, token_pattern=token_pattern)
    return engine.to_ssml(text, wrap_with_speak=wrap_with_speak)


def generate_phoneme_string(
    text: str,
    *,
    lang: str = "hi",
    script: str = "Deva",
    joiner: str = " ",
    token_pattern: str = r"[\w\-’']+|[^\w\s]",
) -> str:
    engine = get_transcriber(lang, script, token_pattern=token_pattern)
    return engine.to_ipa_string(text, joiner=joiner)


__all__ = [
    "PhoneticsProvider",
    "Phoneme",
    "RomanisedPhoneticTranscriber",
    "TranscriberRegistry",
    "TranscriberKey",
    "TransliterationUnavailable",
    "generate_ssml_phonetics",
    "generate_phoneme_string",
    "get_transcriber",
]
