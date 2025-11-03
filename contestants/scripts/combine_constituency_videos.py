#!/usr/bin/env python3
"""
Combine constituency-level video segments into language-specific compilations.

The expected input directory structure is:
<base_dir>/<constituency_id>/<language>/<video files>.mp4

Each run identifies pending constituency + language pairs, concatenates their
clips, and writes them to:
<output_dir>/<language>/<constituency-name>_<constituency-id>_<language>.mp4

Progress is recorded in a JSONL manifest so the script can resume safely.
Each individual clip is trimmed by 0.9 seconds at the start and end before
concatenation so the joins feel seamless. If available, a 1-second disclaimer
image precedes the merged clips and a credits image is appended at the end.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    from moviepy import ImageClip, VideoFileClip, concatenate_videoclips  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    ImageClip = None  # type: ignore
    VideoFileClip = None  # type: ignore
    concatenate_videoclips = None  # type: ignore


# Manifest -------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestEntry:
    constituency_id: str
    language: str
    output_path: str
    sources: Sequence[str]
    created_at: str

    @property
    def key(self) -> Tuple[str, str]:
        return (self.constituency_id, self.language)


def load_manifest(path: Path) -> Tuple[Set[Tuple[str, str]], List[ManifestEntry]]:
    """Load existing manifest entries and return (completed_keys, entries)."""
    completed: Set[Tuple[str, str]] = set()
    entries: List[ManifestEntry] = []
    if not path.exists():
        return completed, entries

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                logging.warning(
                    "Skipping malformed manifest line %s (%s): %s",
                    line_number,
                    path,
                    exc,
                )
                continue

            try:
                entry = ManifestEntry(
                    constituency_id=str(record["constituency_id"]),
                    language=str(record["language"]),
                    output_path=str(record["output_path"]),
                    sources=tuple(record.get("sources", [])),
                    created_at=str(record.get("created_at", "")),
                )
            except KeyError as exc:
                logging.warning(
                    "Skipping manifest line %s (%s). Missing field: %s",
                    line_number,
                    path,
                    exc,
                )
                continue

            completed.add(entry.key)
            entries.append(entry)

    return completed, entries


def append_manifest_entry(path: Path, entry: ManifestEntry) -> None:
    """Append a manifest entry to the JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "constituency_id": entry.constituency_id,
                    "language": entry.language,
                    "output_path": entry.output_path,
                    "sources": list(entry.sources),
                    "created_at": entry.created_at,
                },
                ensure_ascii=False,
            )
            + "\n"
        )


# Lookup ---------------------------------------------------------------------
TRIM_SECONDS = 0.9
IMAGE_CLIP_DURATION = 1.0
DISCLAIMER_IMAGE_PATH = Path("static/background/disclaimer.png")
CREDITS_IMAGE_PATH = Path("static/background/credits.png")

CONSTITUENCY_LOOKUP: Dict[str, str] = {1: 'sheikhpura',
 2: 'kargahar',
 3: 'nabinagar',
 4: 'barauli',
 5: 'baniapur',
 6: 'sahebganj',
 7: 'brahampur',
 8: 'bakhtiarpur',
 9: 'ekma',
 10: 'wazirganj',
 11: 'rajgir (sc)',
 12: 'sursand',
 13: 'mahua',
 14: 'korha (sc)',
 15: 'ziradei',
 16: 'alinagar',
 17: 'maner',
 18: 'atri',
 19: 'barhampur',
 20: 'matihani',
 21: 'daraunda',
 22: 'islampur',
 23: 'runnisaidpur',
 24: 'barachatti (sc)',
 25: 'belsand',
 26: 'bakhri (sc)',
 27: 'raghopur',
 28: 'supaul',
 29: 'jamui',
 30: 'jhanjharpur',
 31: 'ramnagar (sc)',
 32: 'jhajha',
 33: 'kishanganj (kishanganj)',
 34: 'cheria - bariarpur',
 35: 'madhuban',
 36: 'tikari',
 37: 'baisi',
 38: 'sikandra (sc)',
 39: 'raghopur ( vaishali )',
 40: 'narkatia',
 41: 'gaya town',
 42: 'runisaidpur',
 43: 'sultanganj',
 44: 'bankipur',
 45: 'bihariganj',
 46: 'paroo',
 47: 'harnaut',
 48: 'raxaul',
 49: 'bahadurganj',
 50: 'kishanganj',
 51: 'bikram',
 52: 'triveniganj (sc)',
 53: 'araria',
 54: 'katoria (st)',
 55: 'dhauraiya (sc)',
 56: 'muzaffarpur',
 57: 'bachhwara',
 58: 'hayaghat',
 59: 'gora bauram',
 60: 'bahadurpur',
 61: 'khajauli',
 62: 'laukaha',
 63: 'rosera (sc)',
 64: 'garkha (sc)',
 65: 'kasba',
 66: 'tarapur',
 67: 'masaurhi (sc)',
 68: 'nalanda',
 69: 'dinara',
 70: 'aurangabad',
 71: 'banka',
 72: 'nawada',
 73: 'chakai',
 74: 'mahishi',
 75: 'saharsa',
 76: 'sikti',
 77: 'forbesganj',
 78: 'chapra',
 79: 'kurtha',
 80: 'digha',
 81: 'raniganj (sc)',
 82: 'hisua',
 83: 'rafiganj',
 84: 'rajnagar (sc)',
 85: 'gaura bauram',
 86: 'sandesh',
 87: 'barh',
 88: 'hilsa',
 89: 'aurai',
 90: 'harlakhi',
 91: 'dhoraiya (sc)',
 92: 'chanpatia',
 93: 'madhubani',
 94: 'jehanabad',
 95: 'dhaka',
 96: 'sonbarsha (sc)',
 97: 'jagdishpur',
 98: 'siwan',
 99: 'paliganj',
 100: 'obra',
 101: 'marhaura',
 102: 'banmankhi (sc)',
 103: 'makhdumpur (sc)',
 104: 'darbhanga',
 105: 'kusheshwar asthan (sc)',
 106: 'benipur',
 107: 'dumraon',
 108: 'bibhutipur',
 109: 'gopalganj',
 110: 'lauriya',
 111: 'morwa',
 112: 'thakurganj',
 113: 'alamnagar',
 114: 'lakhisarai',
 115: 'keoti',
 116: 'mokama',
 117: 'buxar',
 118: 'katihar',
 119: 'asthawan',
 120: 'sonepur',
 121: 'kalyanpur (sc)',
 122: 'sakra (sc)',
 123: 'munger',
 124: 'vaishali',
 125: 'teghra',
 126: 'bettiah',
 127: 'patna sahib',
 128: 'nirmali',
 129: 'maharajganj',
 130: 'sheohar',
 131: 'jamalpur',
 132: 'darbhanga rural',
 133: 'babubarhi',
 134: 'ghosi',
 135: 'bathnaha (sc)',
 136: 'cheria bariarpur',
 137: 'bisfi',
 138: 'minapur',
 139: 'kochadhaman',
 140: 'mahnar',
 141: 'goriyakothi',
 142: 'fatwah',
 143: 'warsaliganj',
 144: 'kanti',
 145: 'alauli (sc)',
 146: 'karakat',
 147: 'lalganj',
 148: 'motihari',
 149: 'purnia',
 150: 'pranpur',
 151: 'shahpur',
 152: 'patepur (sc)',
 153: 'raghunathpur',
 154: 'riga',
 155: 'bochaha (sc)',
 156: 'dhamdaha',
 157: 'tarari',
 158: 'sarairanjan',
 159: 'nokha',
 160: 'kumhrarh',
 161: 'chiraia',
 162: 'dehri',
 163: 'bochahan (sc)',
 164: 'beldaur',
 165: 'barari',
 166: 'sasaram',
 167: 'kurhani',
 168: 'amarpur',
 169: 'khagaria',
 170: 'hathua',
 171: 'singheshwar (sc)',
 172: 'belaganj',
 173: 'gobindpur',
 174: 'jale',
 175: 'nautan',
 176: 'bodh gaya (sc)',
 177: 'mohiuddinnagar',
 178: 'kadwa',
 179: 'bihpur',
 180: 'begusarai',
 181: 'gaighat',
 182: 'goh',
 183: 'manihari (st)',
 184: 'bhagalpur',
 185: 'barharia',
 186: 'danapur',
 187: 'balrampur',
 188: 'valmiki nagar',
 189: 'madhepura',
 190: 'sahebpur kamal',
 191: 'kutumba (sc)',
 192: 'kesaria',
 193: 'fatuha',
 194: 'rajpur (sc)',
 195: 'chainpur',
 196: 'chenari (sc)',
 197: 'phulwari (sc)',
 198: 'goriakothi',
 199: 'parbatta',
 200: 'raja pakar (sc)',
 201: 'warisnagar',
 202: 'taraiya',
 203: 'rajauli (sc)',
 204: 'arwal',
 205: 'bagaha',
 206: 'baikunthpur',
 207: 'govindganj',
 208: 'ramgarh',
 209: 'rupauli',
 210: 'parsa',
 211: 'kahalgaon',
 212: 'sikta',
 213: 'barbigha',
 214: 'kalyanpur',
 215: 'samastipur',
 216: 'amnour',
 217: 'baruraj',
 218: 'harsidhi (sc)',
 219: 'imamganj (sc)',
 220: 'parihar',
 221: 'gurua',
 222: 'phulparas',
 223: 'kumhrar',
 224: 'nathnagar',
 225: 'simri bakhtiarpur',
 226: 'bajpatti',
 227: 'gopalpur',
 228: 'belhar',
 229: 'darauli (sc)',
 230: 'pirpainti (sc)',
 231: 'manjhi',
 232: 'amour',
 233: 'narpatganj',
 234: 'jokihat',
 235: 'jahanabad',
 236: 'agiaon (sc)',
 237: 'benipatti',
 238: 'arrah',
 239: 'mohania (sc)',
 240: 'ujiarpur',
 241: 'pipra',
 242: 'biharsharif',
 243: 'hajipur',
 244: 'bhore (sc)',
 245: 'sitamarhi',
 246: 'bhorey (sc)',
 247: 'hasanpur',
 248: 'suryagarha',
 249: 'sugauli',
 250: 'bhabua',
 251: 'narkatiaganj',
 252: 'sherghati',
 253: 'daraundha',
 254: 'kuchaikote',
 255: 'chhatapur',
 256: 'barhara'}



def normalise_lookup(mapping: Dict[str, str]) -> Dict[str, str]:
    """Return a lowercase-keyed copy of the provided lookup dictionary."""
    normalised: Dict[str, str] = {}
    for raw_key, raw_value in mapping.items():
        key = str(raw_key).strip().lower()
        value = str(raw_value).strip()
        if not key or not value:
            continue
        normalised[key] = value
    return normalised


def create_image_clip(image_path: Path, duration: float) -> Optional["VideoClip"]:
    """
    Return an ImageClip with the specified duration if the asset exists.

    Returns None when moviepy is unavailable or the file does not exist.
    """
    if ImageClip is None:
        return None
    if not image_path.exists():
        logging.warning("Image asset missing for clip: %s", image_path)
        return None
    try:
        clip = ImageClip(str(image_path))
        return clip.set_duration(duration)
    except Exception as exc:  # pragma: no cover - runtime guard
        logging.error("Unable to create image clip from %s: %s", image_path, exc)
        return None


# Video discovery ------------------------------------------------------------


@dataclass
class VideoGroup:
    constituency_id: str
    language: str
    video_paths: List[Path]


def discover_video_groups(
    base_dir: Path, languages: Optional[Set[str]] = None
) -> Iterable[VideoGroup]:
    """Yield video groups by constituency and language."""
    if not base_dir.exists():
        raise FileNotFoundError(f"Base directory does not exist: {base_dir}")

    for constituency_root in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        constituency_id = constituency_root.name

        for language_root in sorted(p for p in constituency_root.iterdir() if p.is_dir()):
            language = language_root.name
            if languages and language not in languages:
                continue

            video_paths = sorted(
                (path for path in language_root.iterdir() if path.is_file()),
                key=lambda path: path.name,
            )
            if not video_paths:
                continue

            yield VideoGroup(
                constituency_id=constituency_id,
                language=language,
                video_paths=video_paths,
            )


# Video merging --------------------------------------------------------------


def ensure_moviepy_available() -> None:
    if VideoFileClip is None or concatenate_videoclips is None:
        raise SystemExit(
            "moviepy is required. Install it via `pip install moviepy` before running."
        )


def slugify(name: str) -> str:
    """Generate a filesystem-friendly slug."""
    text = name.strip().lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def build_output_filename(
    constituency_id: str,
    language: str,
    lookup: Dict[str, str],
) -> str:
    constituency_name = lookup.get(constituency_id.lower(), constituency_id)
    base = slugify(constituency_name) or constituency_id
    return f"{base}_{constituency_id}_{language}.mp4"


def concatenate_videos(video_paths: Sequence[Path], destination: Path) -> None:
    """Concatenate clips and write a single mp4."""
    ensure_moviepy_available()
    source_clips: List[VideoFileClip] = []
    trimmed_clips: List[VideoFileClip] = []
    image_clips: List["VideoClip"] = []
    try:
        for path in video_paths:
            base_clip = VideoFileClip(str(path))
            source_clips.append(base_clip)

            duration = base_clip.duration or 0.0
            if duration <= TRIM_SECONDS * 2:
                logging.warning(
                    "Clip %s (%.2fs) too short to trim %.2fs; using original clip.",
                    path,
                    duration,
                    TRIM_SECONDS,
                )
                clip_for_concat = base_clip
            else:
                start = TRIM_SECONDS
                end = duration - TRIM_SECONDS
                if hasattr(base_clip, "subclip"):
                    clip_for_concat = base_clip.subclip(start, end)  # legacy MoviePy
                elif hasattr(base_clip, "subclipped"):
                    clip_for_concat = base_clip.subclipped(start, end)
                else:
                    clip_for_concat = base_clip[start:end]

            trimmed_clips.append(clip_for_concat)

        if not trimmed_clips:
            return

        clips_to_concat: List["VideoClip"] = []

        disclaimer_clip = create_image_clip(DISCLAIMER_IMAGE_PATH, IMAGE_CLIP_DURATION)
        if disclaimer_clip is not None:
            clips_to_concat.append(disclaimer_clip)
            image_clips.append(disclaimer_clip)

        clips_to_concat.extend(trimmed_clips)

        credits_clip = create_image_clip(CREDITS_IMAGE_PATH, IMAGE_CLIP_DURATION)
        if credits_clip is not None:
            clips_to_concat.append(credits_clip)
            image_clips.append(credits_clip)

        final_clip = concatenate_videoclips(clips_to_concat, method="compose")
        temp_audio = destination.with_suffix(".temp_audio.m4a")
        destination.parent.mkdir(parents=True, exist_ok=True)
        final_clip.write_videofile(
            str(destination),
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(temp_audio),
        )
    finally:
        if "final_clip" in locals():
            final_clip.close()
        for clip in image_clips:
            clip.close()
        for clip in trimmed_clips:
            clip.close()
        for clip in source_clips:
            if clip not in trimmed_clips:
                clip.close()


# CLI ------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine constituency videos into language-specific compilations.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("static/Bihar/contestants/Combined/done"),
        help="Source directory containing constituency/language folders.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("static/Bihar/contestants/Combined/compiled"),
        help="Destination directory for merged videos.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("static/Bihar/contestants/Combined/compile_manifest.jsonl"),
        help="JSONL manifest to track completed constituency/language outputs.",
    )
    parser.add_argument(
        "--language",
        action="append",
        dest="languages",
        help="Restrict processing to specific languages (repeatable).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild outputs even if they are listed as completed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log planned operations without writing files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of constituency/language groups to process.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (default: INFO).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s %(message)s",
    )

    lookup = normalise_lookup(CONSTITUENCY_LOOKUP)
    if lookup:
        logging.info("Loaded %s constituency names from in-memory lookup", len(lookup))

    if args.languages:
        languages = {lang.strip() for lang in args.languages if lang.strip()}
    else:
        languages = None

    completed_keys, manifest_entries = load_manifest(args.manifest)
    if completed_keys:
        logging.info("Loaded %s completed entries from manifest", len(completed_keys))

    processed = 0
    skipped = 0

    for group in discover_video_groups(args.base_dir, languages):
        key = (group.constituency_id, group.language)
        output_path = args.output_dir / group.language / build_output_filename(
            group.constituency_id,
            group.language,
            lookup,
        )

        if not args.force and key in completed_keys:
            logging.debug("Skipping %s %s (already in manifest)", *key)
            skipped += 1
            continue

        if not args.force and output_path.exists():
            logging.info("Skipping %s %s (output exists)", *key)
            skipped += 1
            continue

        logging.info(
            "Processing constituency %s language %s (%s clips)",
            group.constituency_id,
            group.language,
            len(group.video_paths),
        )
        logging.debug("Source clips: %s", ", ".join(str(p) for p in group.video_paths))
        logging.debug("Destination: %s", output_path)

        if args.dry_run:
            processed += 1
        else:
            try:
                concatenate_videos(group.video_paths, output_path)
            except Exception as exc:  # pragma: no cover - runtime guard
                logging.error(
                    "Failed to combine %s %s: %s", group.constituency_id, group.language, exc
                )
                continue

            entry = ManifestEntry(
                constituency_id=group.constituency_id,
                language=group.language,
                output_path=str(output_path),
                sources=[str(path) for path in group.video_paths],
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            append_manifest_entry(args.manifest, entry)
            completed_keys.add(entry.key)
            processed += 1

        if args.limit and processed >= args.limit:
            logging.info("Reached processing limit (%s); stopping.", args.limit)
            break

    logging.info(
        "Done. Processed %s group(s); skipped %s; manifest entries %s.",
        processed,
        skipped,
        len(completed_keys),
    )
    if args.dry_run:
        logging.info("Dry run complete – no files were written.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
