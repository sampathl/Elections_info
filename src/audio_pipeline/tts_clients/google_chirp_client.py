"""Client for Google Cloud Text-to-Speech using Chirp HD voices."""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Union

from google.cloud import texttospeech
from google.protobuf.json_format import MessageToDict

VoiceOption = Union[str, Mapping[str, Any]]

LANGUAGE_CODE_MAP: Dict[str, str] = {
    "as": "as-IN",
    "bn": "bn-IN",
    "en": "en-IN",
    "gu": "gu-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "ne": "ne-IN",
    "or": "or-IN",
    "pa": "pa-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "ur": "ur-IN",
}

ALLOWED_VOICE_KEYS = {"name", "language_code", "ssml_gender", "custom_voice", "model"}
DEFAULT_CHIRP_MODEL = "hi-IN-Chirp3-HD"


def _normalize_language_code(language_code: str) -> str:
    if not language_code:
        raise ValueError("language_code cannot be empty")
    normalized = language_code.replace("_", "-").lower()
    mapped = LANGUAGE_CODE_MAP.get(normalized)
    if mapped:
        return mapped
    if "-" in normalized:
        lang, region = normalized.split("-", 1)
        return f"{lang}-{region.upper()}"
    return normalized


def _normalize_voice_option(
    option: VoiceOption, default_language_code: str
) -> Dict[str, Any]:
    voice_kwargs: Dict[str, Any] = {
        "language_code": default_language_code,
        "model": DEFAULT_CHIRP_MODEL,
    }
    if isinstance(option, str):
        voice_kwargs["name"] = option
        return voice_kwargs
    if not isinstance(option, Mapping):
        raise TypeError("voice option must be a string or mapping")
    for key, value in option.items():
        if key not in ALLOWED_VOICE_KEYS:
            continue
        if key == "ssml_gender" and isinstance(value, str):
            gender_name = value.upper()
            if not hasattr(texttospeech.SsmlVoiceGender, gender_name):
                raise ValueError(f"Unsupported ssml_gender value: {value}")
            voice_kwargs[key] = getattr(texttospeech.SsmlVoiceGender, gender_name)
        elif key == "language_code" and isinstance(value, str):
            voice_kwargs[key] = _normalize_language_code(value)
        else:
            voice_kwargs[key] = value
    if "language_code" not in voice_kwargs or not voice_kwargs["language_code"]:
        voice_kwargs["language_code"] = default_language_code
    voice_kwargs.setdefault("model", DEFAULT_CHIRP_MODEL)
    return voice_kwargs


def _message_to_dict(message: Any) -> MutableMapping[str, Any]:
    if hasattr(message, "to_dict"):
        return message.to_dict()  # type: ignore[return-value]
    return MessageToDict(message._pb, preserving_proto_field_name=True)  # type: ignore[attr-defined]


@dataclass
class _CyclicVoiceSelector:
    voices: Sequence[VoiceOption]
    shuffle_on_init: bool = True

    def __post_init__(self) -> None:
        if not self.voices:
            raise ValueError("voices cannot be empty")
        ordered = list(self.voices)
        if self.shuffle_on_init:
            random.shuffle(ordered)
        self._voice_cycle = cycle(ordered)

    def next_voice(self) -> VoiceOption:
        return next(self._voice_cycle)


class GoogleTextToSpeechClient:
    """Wraps google-cloud-texttospeech with Chirp support and voice cycling."""

    def __init__(
        self,
        *,
        voice_options: Optional[Sequence[VoiceOption]] = None,
        randomize_voice_cycle: bool = True,
        audio_encoding: texttospeech.AudioEncoding = texttospeech.AudioEncoding.MP3,
        speaking_rate: float = 1.0,
        pitch: float = 0.0,
    ) -> None:
        self._client = texttospeech.TextToSpeechClient()
        self._voice_selector: Optional[_CyclicVoiceSelector] = None
        if voice_options:
            self.set_voice_options(voice_options, randomize_voice_cycle)
        self.audio_encoding = audio_encoding
        self.speaking_rate = speaking_rate
        self.pitch = pitch

    def set_voice_options(
        self,
        voices: Sequence[VoiceOption],
        shuffle_on_init: bool = True,
    ) -> None:
        self._voice_selector = _CyclicVoiceSelector(
            voices=voices, shuffle_on_init=shuffle_on_init
        )

    def synthesize(
        self,
        text_or_ssml: str,
        language_code: str,
        output_path: Union[str, Path],
        *,
        is_ssml: bool = False,
        audio_encoding: Optional[texttospeech.AudioEncoding] = None,
        speaking_rate: Optional[float] = None,
        pitch: Optional[float] = None,
    ) -> Dict[str, Any]:
        normalized_language = _normalize_language_code(language_code)
        input_config = (
            texttospeech.SynthesisInput(ssml=text_or_ssml)
            if is_ssml
            else texttospeech.SynthesisInput(text=text_or_ssml)
        )
        voice_kwargs: Dict[str, Any] = {
            "language_code": normalized_language,
            "model": DEFAULT_CHIRP_MODEL,
        }
        if self._voice_selector:
            voice_kwargs.update(
                _normalize_voice_option(
                    self._voice_selector.next_voice(), normalized_language
                )
            )
        voice_params = texttospeech.VoiceSelectionParams(**voice_kwargs)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding or self.audio_encoding,
            speaking_rate=speaking_rate if speaking_rate is not None else self.speaking_rate,
            pitch=pitch if pitch is not None else self.pitch,
        )

        response = self._client.synthesize_speech(
            request=texttospeech.SynthesizeSpeechRequest(
                input=input_config, voice=voice_params, audio_config=audio_config
            )
        )

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(response.audio_content)

        response_dict = _message_to_dict(response)
        response_dict.pop("audio_content", None)

        return {
            "response": response_dict,
            "audio_file_path": str(output_file),
            "voice_used": voice_kwargs,
            "language": normalized_language,
        }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Synthesize audio with Google Cloud Text-to-Speech (Chirp HD)."
    )
    parser.add_argument(
        "text",
        default="""<speak> उम्मीदवार का नाम: <phoneme alphabet="ipa" ph="mənod͡ʒ">मनोज</phoneme> <phoneme alphabet="ipa" ph="mənzil">मंज़िल</phoneme><mark name="name"/>, <break time='200ms'/> <phoneme alphabet="ipa" ph="siːpiːaːiː">सीपीआई</phoneme> <phoneme alphabet="ipa" ph="məl">मल</phoneme> <phoneme alphabet="ipa" ph="L">L</phoneme> पार्टी से संबद्ध हैं<mark name="party"/>, उम्र ३६ वर्ष<mark name="age"/>, स्नातक शिक्षा प्राप्त है (B.A. from H.D. Jain College, Ara in 2015)<mark name="education"/>, <break time='200ms'/> ३० आपराधिक मामले दर्ज हैं<mark name="criminal_cases"/>, घोषित संपत्ति ३ लाख की है<mark name="assets"/> और घोषित ऋण १० हज़ार का है<mark name="liabilities"/></speak>""",
        help="Text or SSML to synthesize. Pass --ssml when providing SSML input.",
    )
    parser.add_argument(
        "--language",
        default="en-IN",
        help="Two-letter language alias or full Google TTS language code (default: en-IN).",
    )
    parser.add_argument(
        "--output",
        default="output.mp3",
        help="File path to store the generated audio (default: output.mp3).",
    )
    parser.add_argument(
        "--ssml",
        action="store_true",
        help="Treat the provided text argument as SSML.",
    )
    parser.add_argument(
        "--voice",
        action="append",
        dest="voices",
        help="Optional voice name or JSON object describing a voice. "
        "Can be supplied multiple times. Example: --voice en-IN-Chirp-v3-1 "
        "or --voice '{\"name\": \"en-IN-Chirp-v3-2\", \"ssml_gender\": \"FEMALE\"}'.",
    )
    parser.add_argument(
        "--preserve-order",
        action="store_true",
        help="Disable shuffling when cycling through provided voices.",
    )
    args = parser.parse_args()

    parsed_voice_options: Optional[list[VoiceOption]] = None
    if args.voices:
        parsed_voice_options = []
        for voice_arg in args.voices:
            try:
                parsed_voice_options.append(json.loads(voice_arg))
            except json.JSONDecodeError:
                parsed_voice_options.append(voice_arg)

    client = GoogleTextToSpeechClient(
        voice_options=parsed_voice_options,
        randomize_voice_cycle=not args.preserve_order,
    )
    metadata = client.synthesize(
        text_or_ssml=args.text,
        language_code=args.language,
        output_path=args.output,
        is_ssml=args.ssml,
    )
    print(f"Saved audio to: {metadata['audio_file_path']}")
    print("Response metadata (audio content omitted):")
    print(json.dumps(metadata, indent=2))
