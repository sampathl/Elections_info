#!/usr/bin/env python3
"""Upload posts to Reddit via PRAW.

The script supports single-post CLI usage or bulk uploads described in a JSON file.

Credential lookup order:
1. Explicit JSON file passed via --credentials (keys: client_id, client_secret, username, password, user_agent)
2. Environment variables with the same names in upper case (e.g. REDDIT_CLIENT_ID).

Example posts file structure:
{
  "posts": [
    {
      "subreddit": "test",
      "title": "Example text post",
      "body": "Body text",
      "flair_id": "optional",
      "nsfw": false,
      "spoiler": false,
      "send_replies": true
    },
    {
      "subreddit": "test",
      "title": "Example link post",
      "url": "https://example.com"
    }
  ]
}
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import praw
    from praw.exceptions import APIException, PRAWException
except ImportError as exc:  # pragma: no cover
    raise SystemExit("praw package is required. Install it with `pip install praw`.") from exc

CredentialDict = Dict[str, str]
PostSpec = Dict[str, Any]

REQUIRED_CREDENTIAL_KEYS = {"client_id", "client_secret", "username", "password", "user_agent"}
ENV_PREFIX = "REDDIT_"


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


def build_reddit_client(creds: CredentialDict) -> praw.Reddit:
    return praw.Reddit(
        client_id=creds["client_id"],
        client_secret=creds["client_secret"],
        username=creds["username"],
        password=creds["password"],
        user_agent=creds["user_agent"],
    )


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
    if not isinstance(posts, Iterable):
        raise ValueError("Posts file must contain a list of posts or a {\"posts\": [...]} object")
    normalized: List[PostSpec] = []
    for raw in posts:
        if not isinstance(raw, dict):
            raise ValueError("Each post entry must be a JSON object")
        normalized.append({k: v for k, v in raw.items()})
    return normalized


def post_from_args(args: argparse.Namespace) -> List[PostSpec]:
    if not args.title or not args.subreddit:
        raise ValueError("--title and --subreddit are required unless --posts-file is provided")
    mode_fields = [bool(args.body), bool(args.url), bool(args.image)]
    if sum(mode_fields) != 1:
        raise ValueError("Provide exactly one of --body, --url, or --image when creating a single post")
    spec: PostSpec = {
        "title": args.title,
        "subreddit": args.subreddit,
        "body": args.body,
        "url": args.url,
        "image_path": args.image,
        "flair_id": args.flair_id,
        "flair_text": args.flair_text,
        "nsfw": args.nsfw,
        "spoiler": args.spoiler,
        "send_replies": not args.no_replies,
    }
    return [spec]


def normalize_post_spec(spec: PostSpec) -> PostSpec:
    if "title" not in spec or "subreddit" not in spec:
        raise ValueError("Each post requires 'title' and 'subreddit'")
    title = str(spec["title"]).strip()
    subreddit = str(spec["subreddit"]).strip()
    if not title:
        raise ValueError("Post title cannot be empty")
    if not subreddit:
        raise ValueError("Subreddit cannot be empty")
    body = spec.get("body")
    url = spec.get("url")
    image_path = spec.get("image_path") or spec.get("image")
    provided = [bool(body), bool(url), bool(image_path)]
    if sum(provided) != 1:
        raise ValueError(f"Post '{title}' must define exactly one of 'body', 'url', or 'image_path'")
    kind: str
    payload: PostSpec = {
        "title": title,
        "subreddit": subreddit,
        "flair_id": spec.get("flair_id"),
        "flair_text": spec.get("flair_text"),
        "nsfw": bool(spec.get("nsfw", False)),
        "spoiler": bool(spec.get("spoiler", False)),
        "send_replies": bool(spec.get("send_replies", True)),
    }
    if image_path:
        path = Path(image_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        kind = "image"
        payload["image_path"] = str(path)
    elif url:
        kind = "link"
        payload["url"] = str(url)
    else:
        kind = "self"
        payload["body"] = str(body)
    payload["kind"] = kind
    return payload


def submit_post(reddit: praw.Reddit, spec: PostSpec, dry_run: bool = False) -> PostSpec:
    result: PostSpec = {
        "title": spec["title"],
        "subreddit": spec["subreddit"],
        "kind": spec["kind"],
    }
    if dry_run:
        result["status"] = "skipped"
        return result
    try:
        subreddit = reddit.subreddit(spec["subreddit"])
        flair_kwargs = {
            "flair_id": spec.get("flair_id"),
            "flair_text": spec.get("flair_text"),
        }
        flair_kwargs = {k: v for k, v in flair_kwargs.items() if v}
        kwargs = {
            "nsfw": spec.get("nsfw", False),
            "spoiler": spec.get("spoiler", False),
            "send_replies": spec.get("send_replies", True),
            **flair_kwargs,
        }
        if spec["kind"] == "image":
            submission = subreddit.submit_image(spec["title"], image_path=spec["image_path"], **kwargs)
        elif spec["kind"] == "link":
            submission = subreddit.submit(spec["title"], url=spec["url"], **kwargs)
        else:
            submission = subreddit.submit(spec["title"], selftext=spec.get("body", ""), **kwargs)
        result["status"] = "posted"
        result["submission_id"] = submission.id
        result["permalink"] = f"https://www.reddit.com{submission.permalink}"
    except APIException as exc:
        result["status"] = "failed"
        result["error"] = f"{exc.error_type}: {exc.message}"
    except PRAWException as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
    return result


def write_results(results: List[PostSpec], output_path: Optional[str]) -> Optional[Path]:
    if not results:
        return None
    target = Path(output_path).expanduser() if output_path else None
    if not target:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target = Path(__file__).resolve().with_name(f"reddit_post_results_{timestamp}.json")
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Reddit posts with optional bulk JSON input.")
    parser.add_argument("--credentials", help="Path to credentials JSON file")
    parser.add_argument("--posts-file", help="JSON file containing posts to upload")
    parser.add_argument("--subreddit", help="Target subreddit for single post mode")
    parser.add_argument("--title", help="Post title for single post mode")
    parser.add_argument("--body", help="Text body for self post")
    parser.add_argument("--url", help="Link URL for link post")
    parser.add_argument("--image", help="Image path for image post")
    parser.add_argument("--flair-id", help="Flair template ID")
    parser.add_argument("--flair-text", help="Flair text")
    parser.add_argument("--nsfw", action="store_true", help="Mark post as NSFW")
    parser.add_argument("--spoiler", action="store_true", help="Mark post as spoiler")
    parser.add_argument("--no-replies", action="store_true", help="Disable inbox replies to comments")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without uploading")
    parser.add_argument("--results-file", help="Where to write upload results JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        creds = load_credentials(args.credentials)
    except Exception as exc:
        raise SystemExit(f"Credential error: {exc}")
    reddit = build_reddit_client(creds)
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
        outcome = submit_post(reddit, spec, dry_run=args.dry_run)
        results.append(outcome)
        status = outcome.get("status", "unknown")
        message = outcome.get("error") or outcome.get("permalink") or ""
        print(f"[{status.upper()}] r/{outcome['subreddit']} - {outcome['title']} {message}")

    saved_path = write_results(results, args.results_file)
    if saved_path:
        print(f"Results saved to {saved_path}")
    if args.dry_run:
        print("Dry run complete. No posts were uploaded.")


if __name__ == "__main__":
    main()
