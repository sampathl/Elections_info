#!/usr/bin/env python3
"""Upload Facebook Page posts through the Graph API.

The script supports single-post CLI usage and JSON-described bulk uploads.
Each post may be a status update, link share, photo, or video, with optional
scheduled publication.

Credential lookup order:
1. Credentials JSON passed with --credentials (keys: access_token, page_id, optional graph_version)
2. Environment variables prefixed with FACEBOOK_, e.g. FACEBOOK_ACCESS_TOKEN.

Example posts file:
{
  "posts": [
    {
      "message": "Hello Facebook!",
      "link_url": "https://example.com"
    },
    {
      "message": "Photo post",
      "image_url": "https://example.com/image.jpg"
    },
    {
      "message": "Scheduled status",
      "scheduled_time": 1735689600
    }
  ]
}
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import requests
    from requests import Response
    from requests.exceptions import RequestException
except ImportError as exc:  # pragma: no cover
    raise SystemExit("requests package is required. Install it with `pip install requests`.") from exc

CredentialDict = Dict[str, str]
PostSpec = Dict[str, Any]

REQUIRED_CREDENTIAL_KEYS = {"access_token", "page_id"}
ENV_PREFIX = "FACEBOOK_"
DEFAULT_GRAPH_VERSION = "v19.0"
GRAPH_BASE_URL = "https://graph.facebook.com"


class GraphAPIError(RuntimeError):
    """Raised when the Graph API returns an error payload."""


def normalize_graph_version(version: Optional[str]) -> str:
    if not version:
        return DEFAULT_GRAPH_VERSION
    version = version.strip()
    if not version:
        return DEFAULT_GRAPH_VERSION
    if version.startswith("v"):
        return version
    return f"v{version}"


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
        creds.update({k: str(v) for k, v in data.items()})
    for key in REQUIRED_CREDENTIAL_KEYS | {"graph_version"}:
        env_key = f"{ENV_PREFIX}{key.upper()}"
        if key not in creds and (value := os.getenv(env_key)):
            creds[key] = value
    missing = [key for key in REQUIRED_CREDENTIAL_KEYS if key not in creds]
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"Missing credential values for: {joined}")
    return creds


def graph_url(graph_version: str, path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    version = normalize_graph_version(graph_version)
    return f"{GRAPH_BASE_URL}/{version}{path}"


def parse_graph_response(response: Response) -> Dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:  # pragma: no cover
        raise GraphAPIError(f"Invalid JSON response: {response.text}") from exc
    if response.status_code >= 400 or "error" in payload:
        error = payload.get("error", {})
        message = error.get("message") or response.text
        code = error.get("code")
        raise GraphAPIError(f"Graph API error ({code}): {message}")
    return payload


def graph_post(config: Dict[str, str], path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    url = graph_url(config["graph_version"], path)
    body = {k: v for k, v in data.items() if v is not None}
    body["access_token"] = config["access_token"]
    try:
        response = requests.post(url, data=body)
    except RequestException as exc:
        raise GraphAPIError(f"Request failed: {exc}") from exc
    return parse_graph_response(response)


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


def normalize_scheduled_time(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            try:
                dt = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("scheduled_time must be a UNIX timestamp or ISO datetime string") from exc
            return int(dt.timestamp())
    raise ValueError("scheduled_time must be numeric or ISO datetime string")


def normalize_url_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [value]
    urls: List[str] = []
    for item in items:
        if item is None:
            continue
        url = str(item).strip()
        if url:
            urls.append(url)
    return urls


def normalize_post_spec(spec: PostSpec) -> PostSpec:
    message = str(spec.get("message", "")) if spec.get("message") is not None else ""
    link_url = spec.get("link_url") or spec.get("linkUrl")
    scheduled_time = normalize_scheduled_time(spec.get("scheduled_time") or spec.get("scheduledTime"))
    unpublished_type = spec.get("unpublished_content_type") or spec.get("unpublishedContentType")

    image_urls = normalize_url_list(spec.get("image_urls") or spec.get("imageUrls"))
    video_urls = normalize_url_list(spec.get("video_urls") or spec.get("videoUrls"))
    image_urls.extend(normalize_url_list(spec.get("image_url") or spec.get("imageUrl")))
    video_urls.extend(normalize_url_list(spec.get("video_url") or spec.get("videoUrl")))

    media_items_raw = spec.get("media_items") or spec.get("mediaItems")
    attachments: List[Dict[str, str]] = []

    if media_items_raw is not None:
        if not isinstance(media_items_raw, list):
            raise ValueError("media_items must be a list")
        for item in media_items_raw:
            if not isinstance(item, dict):
                raise ValueError("Each media_items entry must be an object")
            kind_raw = item.get("kind") or item.get("type") or item.get("media_type")
            kind = (str(kind_raw).lower() if kind_raw else "")
            url = item.get("url") or item.get("image_url") or item.get("video_url")
            if not url:
                raise ValueError("media_items entries require a URL field")
            url_str = str(url)
            if kind in {"video", "videos"} or "video" in kind:
                attachments.append({"kind": "video", "url": url_str})
            elif kind in {"image", "photo", ""} or "image" in kind or "photo" in kind:
                attachments.append({"kind": "photo", "url": url_str})
            else:
                raise ValueError("media_items entries must have kind/type of 'image' or 'video'")

    for url in image_urls:
        attachments.append({"kind": "photo", "url": url})
    for url in video_urls:
        attachments.append({"kind": "video", "url": url})

    if attachments and link_url:
        raise ValueError("Cannot include link_url when image or video URLs are provided")
    if not any((message, link_url, attachments)):
        raise ValueError("Post must include a message, link_url, or media URLs")

    # Deduplicate attachments while preserving order
    seen: Set[Tuple[str, str]] = set()
    deduped: List[Dict[str, str]] = []
    for attachment in attachments:
        key = (attachment["kind"], attachment["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(attachment)
    attachments = deduped

    if len(attachments) > 10:
        raise ValueError("Facebook supports up to 10 attached media items per post")

    payload: PostSpec = {
        "message": message.strip() if message else "",
        "kind": "status",
        "scheduled_time": scheduled_time,
        "unpublished_content_type": unpublished_type,
    }

    if attachments:
        if len(attachments) == 1:
            media = attachments[0]
            payload["kind"] = "video" if media["kind"] == "video" else "photo"
            if media["kind"] == "video":
                payload["video_url"] = media["url"]
            else:
                payload["image_url"] = media["url"]
        else:
            payload["kind"] = "media_group"
            payload["attachments"] = attachments
    elif link_url:
        payload["kind"] = "link"
        payload["link_url"] = str(link_url)
    else:
        payload["link_url"] = None

    return payload


def submit_post(config: Dict[str, str], spec: PostSpec, dry_run: bool) -> PostSpec:
    result: PostSpec = {
        "kind": spec["kind"],
        "message": spec.get("message"),
    }
    if dry_run:
        result["status"] = "skipped"
        return result
    payload: Dict[str, Any] = {}
    if spec.get("message"):
        payload["message"] = spec["message"]
    scheduled_time = spec.get("scheduled_time")
    if scheduled_time:
        payload["scheduled_publish_time"] = scheduled_time
        payload["published"] = False
        if spec.get("unpublished_content_type"):
            payload["unpublished_content_type"] = spec["unpublished_content_type"]
    if spec["kind"] == "photo":
        payload["url"] = spec["image_url"]
        response = graph_post(config, f"/{config['page_id']}/photos", payload)
    elif spec["kind"] == "video":
        payload["file_url"] = spec["video_url"]
        response = graph_post(config, f"/{config['page_id']}/videos", payload)
    elif spec["kind"] == "media_group":
        attachments = spec.get("attachments") or []
        if not attachments:
            raise GraphAPIError("No attachments provided for media_group post")
        attached_ids: List[str] = []
        for attachment in attachments:
            kind = attachment.get("kind")
            url = attachment.get("url")
            if not url:
                raise GraphAPIError("Attachment missing URL")
            if kind == "video":
                upload_payload = {"file_url": url, "published": False}
                upload = graph_post(config, f"/{config['page_id']}/videos", upload_payload)
            else:
                upload_payload = {"url": url, "published": False}
                upload = graph_post(config, f"/{config['page_id']}/photos", upload_payload)
            media_id = upload.get("id")
            if not media_id:
                raise GraphAPIError("Graph API did not return an id for attached media")
            attached_ids.append(media_id)
        for idx, media_id in enumerate(attached_ids):
            payload[f"attached_media[{idx}]"] = json.dumps({"media_fbid": media_id})
        response = graph_post(config, f"/{config['page_id']}/feed", payload)
        result["attached_media_ids"] = attached_ids
    elif spec["kind"] == "link":
        if spec.get("link_url"):
            payload["link"] = spec["link_url"]
        response = graph_post(config, f"/{config['page_id']}/feed", payload)
    else:
        response = graph_post(config, f"/{config['page_id']}/feed", payload)
    post_id = response.get("id") or response.get("post_id")
    if not post_id:
        raise GraphAPIError("Graph API did not return a post id")
    result["status"] = "posted"
    result["post_id"] = post_id
    if scheduled_time:
        result["scheduled_publish_time"] = scheduled_time
    else:
        result["permalink"] = f"https://www.facebook.com/{post_id}"
    return result


def write_results(results: List[PostSpec], output_path: Optional[str]) -> Optional[Path]:
    if not results:
        return None
    target = Path(output_path).expanduser() if output_path else None
    if not target:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target = Path(__file__).resolve().with_name(f"facebook_post_results_{timestamp}.json")
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "results": results,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
    return target


def post_from_args(args: argparse.Namespace) -> List[PostSpec]:
    image_urls = args.image_urls or []
    video_urls = args.video_urls or []
    if not any((args.message, args.link_url, image_urls, video_urls)):
        raise ValueError(
            "Provide at least --message, --link-url, --image-url, or --video-url when not using --posts-file"
        )
    spec: PostSpec = {
        "message": args.message,
        "link_url": args.link_url,
        "image_urls": image_urls,
        "video_urls": video_urls,
        "scheduled_time": args.scheduled_time,
        "unpublished_content_type": args.unpublished_content_type,
    }
    return [spec]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Facebook Page posts via the Graph API.")
    parser.add_argument("--credentials", help="Path to credentials JSON file")
    parser.add_argument("--posts-file", help="JSON file describing posts to upload")
    parser.add_argument("--message", help="Status message for single post mode")
    parser.add_argument("--link-url", help="Link URL for link post")
    parser.add_argument(
        "--image-url",
        dest="image_urls",
        action="append",
        help="Image URL for photo post (repeat for multiple)",
    )
    parser.add_argument(
        "--video-url",
        dest="video_urls",
        action="append",
        help="Video URL for video post (repeat for multiple)",
    )
    parser.add_argument("--scheduled-time", dest="scheduled_time", help="UNIX timestamp or ISO datetime for scheduled publish")
    parser.add_argument("--unpublished-content-type", help="Optional unpublished content type (REVIEWABLE, SCHEDULED, etc.)")
    parser.add_argument("--graph-version", help="Graph API version (defaults to v19.0)")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without publishing")
    parser.add_argument("--results-file", help="Where to write upload results JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        creds = load_credentials(args.credentials)
    except Exception as exc:
        raise SystemExit(f"Credential error: {exc}")

    graph_version = args.graph_version or creds.get("graph_version") or os.getenv(f"{ENV_PREFIX}GRAPH_VERSION")
    config: Dict[str, str] = {
        "access_token": creds["access_token"],
        "page_id": creds["page_id"],
        "graph_version": normalize_graph_version(graph_version),
    }

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
        try:
            outcome = submit_post(config, spec, dry_run=args.dry_run)
        except Exception as exc:
            outcome = {
                "kind": spec["kind"],
                "message": spec.get("message"),
                "status": "failed",
                "error": str(exc),
            }
        results.append(outcome)
        status = outcome.get("status", "unknown")
        detail = outcome.get("permalink") or outcome.get("error") or outcome.get("post_id") or ""
        preview = (spec.get("message") or spec.get("link_url") or spec.get("image_url") or spec.get("video_url") or "[no content]").replace("\n", " ")[:60]
        print(f"[{status.upper()}] {preview} {detail}")

    saved_path = write_results(results, args.results_file)
    if saved_path:
        print(f"Results saved to {saved_path}")
    if args.dry_run:
        print("Dry run complete. No posts were published.")


if __name__ == "__main__":
    main()
