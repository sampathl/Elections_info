#!/usr/bin/env python3
"""Upload posts to Twitter/X via Tweepy.

The script supports single-post CLI usage and bulk uploads described in a JSON file.

Credential lookup order:
1. Explicit JSON file passed via --credentials (keys: api_key, api_secret, access_token, access_token_secret, bearer_token)
2. Environment variables prefixed with TWITTER_, e.g. TWITTER_API_KEY.

Example posts file:
{
  "posts": [
    {
      "text": "Example tweet",
      "media_paths": ["~/Pictures/sample.jpg"],
      "reply_tweet_id": "1234567890"
    },
    {
      "text": "Another tweet"
    }
  ]
}
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import tweepy
    from tweepy.errors import TweepyException
except ImportError as exc:  # pragma: no cover
    raise SystemExit("tweepy package is required. Install it with `pip install tweepy`.") from exc

CredentialDict = Dict[str, str]
PostSpec = Dict[str, Any]

REQUIRED_CREDENTIAL_KEYS = {
    "api_key",
    "api_secret",
    "access_token",
    "access_token_secret",
    "bearer_token",
}
ENV_PREFIX = "TWITTER_"


def load_credentials(path: Optional[str]) -> CredentialDict:
    creds: Dict[str, str] = {}
    if path:
        config_path = Path(path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        if not isinstance(data, dict):
            raise ValueError("Credentials file must contain a JSON object")
        creds.update({k: str(v) for k, v in data.items() if k in REQUIRED_CREDENTIAL_KEYS})
    for key in REQUIRED_CREDENTIAL_KEYS:
        if key not in creds:
            env_key = f"{ENV_PREFIX}{key.upper()}"
            value = os.getenv(env_key)
            if value:
                creds[key] = value
    missing = REQUIRED_CREDENTIAL_KEYS - creds.keys()
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"Missing credential values for: {joined}")
    return creds


def build_clients(creds: CredentialDict) -> tuple[tweepy.Client, tweepy.API]:
    oauth1 = tweepy.OAuth1UserHandler(
        creds["api_key"],
        creds["api_secret"],
        creds["access_token"],
        creds["access_token_secret"],
    )
    api_v1 = tweepy.API(oauth1)
    client_v2 = tweepy.Client(
        bearer_token=creds["bearer_token"],
        consumer_key=creds["api_key"],
        consumer_secret=creds["api_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_token_secret"],
    )
    return client_v2, api_v1


def load_posts_from_file(path: str) -> List[PostSpec]:
    file_path = Path(path).expanduser()
    if not file_path.exists():
        raise FileNotFoundError(f"Posts file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if isinstance(data, dict) and "posts" in data:
        posts = data["posts"]
    else:
        posts = data
    if not isinstance(posts, list):
        raise ValueError("Posts file must contain a list of posts or a {\"posts\": [...]} object")
    normalized: List[PostSpec] = []
    for raw in posts:
        if not isinstance(raw, dict):
            raise ValueError("Each post entry must be a JSON object")
        normalized.append({k: v for k, v in raw.items()})
    return normalized


def post_from_args(args: argparse.Namespace) -> List[PostSpec]:
    if not args.text:
        raise ValueError("--text is required unless --posts-file is provided")
    spec: PostSpec = {
        "text": args.text,
        "media_paths": args.media or [],
        "reply_tweet_id": args.reply_to,
        "quote_tweet_id": args.quote_tweet_id,
    }
    return [spec]


def normalize_post_spec(spec: PostSpec) -> PostSpec:
    if "text" not in spec:
        raise ValueError("Each post must include 'text'")
    text = str(spec["text"]).strip()
    if not text:
        raise ValueError("Tweet text cannot be empty")
    if len(text) > 280:
        raise ValueError("Tweet text cannot exceed 280 characters")
    media_paths_raw = spec.get("media_paths") or spec.get("media")
    if media_paths_raw is None:
        media_paths: List[str] = []
    elif isinstance(media_paths_raw, (list, tuple)):
        media_paths = [str(path) for path in media_paths_raw]
    else:
        media_paths = [str(media_paths_raw)]
    resolved_media: List[str] = []
    for path in media_paths:
        expanded = Path(path).expanduser()
        if not expanded.exists():
            raise FileNotFoundError(f"Media file not found: {expanded}")
        resolved_media.append(str(expanded))
    if len(resolved_media) > 4:
        raise ValueError("Twitter only allows up to 4 media attachments per tweet")
    reply_tweet_id = spec.get("reply_tweet_id") or spec.get("reply_to")
    quote_tweet_id = spec.get("quote_tweet_id") or spec.get("quote_to")
    payload: PostSpec = {
        "text": text,
        "media_paths": resolved_media,
        "reply_tweet_id": str(reply_tweet_id) if reply_tweet_id else None,
        "quote_tweet_id": str(quote_tweet_id) if quote_tweet_id else None,
    }
    return payload


def submit_post(
    client: tweepy.Client,
    api: tweepy.API,
    spec: PostSpec,
    dry_run: bool = False,
) -> PostSpec:
    result: PostSpec = {
        "text": spec["text"],
        "media_paths": spec.get("media_paths", []),
    }
    if dry_run:
        result["status"] = "skipped"
        return result
    media_ids: List[str] = []
    try:
        for media_path in spec.get("media_paths", []):
            upload = api.media_upload(media_path)
            media_ids.append(upload.media_id_string)
        tweet_kwargs: Dict[str, Any] = {"text": spec["text"]}
        if media_ids:
            tweet_kwargs["media_ids"] = media_ids
        if spec.get("reply_tweet_id"):
            tweet_kwargs["reply_tweet_id"] = spec["reply_tweet_id"]
        if spec.get("quote_tweet_id"):
            tweet_kwargs["quote_tweet_id"] = spec["quote_tweet_id"]
        response = client.create_tweet(**tweet_kwargs)
        tweet_id = response.data.get("id") if response and response.data else None
        result["status"] = "posted"
        result["tweet_id"] = tweet_id
        if tweet_id:
            result["url"] = f"https://twitter.com/i/web/status/{tweet_id}"
    except TweepyException as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    return result


def write_results(results: List[PostSpec], output_path: Optional[str]) -> Optional[Path]:
    if not results:
        return None
    target = Path(output_path).expanduser() if output_path else None
    if not target:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target = Path(__file__).resolve().with_name(f"twitter_post_results_{timestamp}.json")
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Twitter/X posts with optional bulk JSON input.")
    parser.add_argument("--credentials", help="Path to credentials JSON file")
    parser.add_argument("--posts-file", help="JSON file containing posts to upload")
    parser.add_argument("--text", help="Tweet text for single post mode")
    parser.add_argument("--media", action="append", help="Path to media file (repeat for multiple)")
    parser.add_argument("--reply-to", dest="reply_to", help="Tweet ID to reply to")
    parser.add_argument("--quote-tweet-id", help="Tweet ID to quote")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without publishing")
    parser.add_argument("--results-file", help="Where to write upload results JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        creds = load_credentials(args.credentials)
    except Exception as exc:
        raise SystemExit(f"Credential error: {exc}")
    try:
        client, api = build_clients(creds)
    except Exception as exc:
        raise SystemExit(f"Client initialization error: {exc}")

    posts: List[PostSpec] = []
    if args.posts_file:
        try:
            posts.extend(load_posts_from_file(args.posts_file))
        except Exception as exc:
            raise SystemExit(f"Post file error: {exc}")
    else:
        try:
            posts.extend(post_from_args(args))
        except Exception as exc:
            raise SystemExit(str(exc))

    normalized: List[PostSpec] = []
    for spec in posts:
        try:
            normalized.append(normalize_post_spec(spec))
        except Exception as exc:
            raise SystemExit(f"Validation error: {exc}")

    results: List[PostSpec] = []
    for spec in normalized:
        outcome = submit_post(client, api, spec, dry_run=args.dry_run)
        results.append(outcome)
        status = outcome.get("status", "unknown")
        message = outcome.get("error") or outcome.get("url") or ""
        preview = spec["text"].replace("\n", " ")[:60]
        print(f"[{status.upper()}] {preview} {message}")

    saved_path = write_results(results, args.results_file)
    if saved_path:
        print(f"Results saved to {saved_path}")
    if args.dry_run:
        print("Dry run complete. No tweets were published.")


if __name__ == "__main__":
    main()
