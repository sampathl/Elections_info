#!/usr/bin/env python3
"""Upload Instagram posts through the Graph API.

The script supports single-post CLI usage as well as bulk uploads defined
in a JSON file. Each post can publish a single image/video or a carousel
of up to 20 media items.

Credential lookup order:
1. Credentials JSON passed with --credentials (keys: access_token, ig_user_id, optional graph_version)
2. Environment variables prefixed with INSTAGRAM_, e.g. INSTAGRAM_ACCESS_TOKEN.

Example posts file:
{
  "posts": [
    {
      "caption": "Hello Instagram!",
      "image_url": "https://example.com/image.jpg"
    },
    {
      "caption": "Video upload",
      "video_url": "https://example.com/video.mp4",
      "thumb_offset": 3
    }
  ]
}
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
    from requests import Response
    from requests.exceptions import RequestException
except ImportError as exc:  # pragma: no cover
    raise SystemExit("requests package is required. Install it with `pip install requests`.") from exc

CredentialDict = Dict[str, str]
PostSpec = Dict[str, Any]

REQUIRED_CREDENTIAL_KEYS = {"access_token", "ig_user_id"}
ENV_PREFIX = "INSTAGRAM_"
DEFAULT_GRAPH_VERSION = "v19.0"
GRAPH_BASE_URL = "https://graph.facebook.com"
READY_CONTAINER_STATUSES = {"FINISHED", "READY", "PUBLISHED"}


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


def graph_get(config: Dict[str, str], path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = graph_url(config["graph_version"], path)
    query = {"access_token": config["access_token"]}
    if params:
        query.update({k: v for k, v in params.items() if v is not None})
    try:
        response = requests.get(url, params=query)
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


def parse_user_tags(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"user_tags must be valid JSON: {exc}") from exc
        return value
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    raise ValueError("user_tags must be provided as JSON text, list, or dict")


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


def coerce_optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("thumb_offset must be a number") from exc


def normalize_post_spec(spec: PostSpec) -> PostSpec:
    caption = str(spec.get("caption", "")) if spec.get("caption") is not None else ""
    location_id = spec.get("location_id") or spec.get("locationId")
    user_tags = parse_user_tags(spec.get("user_tags") or spec.get("userTags"))
    thumb_offset = coerce_optional_float(spec.get("thumb_offset") or spec.get("thumbOffset"))

    media_items_raw = spec.get("media_items") or spec.get("mediaItems")
    children: List[PostSpec] = []

    if media_items_raw is not None:
        if not isinstance(media_items_raw, list):
            raise ValueError("media_items must be a list")
        for item in media_items_raw:
            if not isinstance(item, dict):
                raise ValueError("Each media_items entry must be an object")
            kind_raw = item.get("kind") or item.get("type") or item.get("media_type")
            kind = (str(kind_raw).lower() if kind_raw else "")
            if kind in {"video", "videos"} or "video" in kind:
                url = item.get("video_url") or item.get("url")
                if not url:
                    raise ValueError("Video media item requires 'video_url' or 'url'")
                child: PostSpec = {"kind": "video", "video_url": str(url)}
                offset = coerce_optional_float(item.get("thumb_offset") or item.get("thumbOffset"))
                if offset is not None:
                    child["thumb_offset"] = offset
                children.append(child)
            elif kind in {"image", "photo", ""} or "image" in kind or "photo" in kind:
                url = item.get("image_url") or item.get("url")
                if not url:
                    raise ValueError("Image media item requires 'image_url' or 'url'")
                children.append({"kind": "image", "image_url": str(url)})
            else:
                raise ValueError("media_items entries must have kind/type of 'image' or 'video'")
    else:
        image_urls = normalize_url_list(spec.get("image_urls") or spec.get("imageUrls"))
        video_urls = normalize_url_list(spec.get("video_urls") or spec.get("videoUrls"))
        if not image_urls:
            image_urls = normalize_url_list(spec.get("image_url") or spec.get("imageUrl"))
        if not video_urls:
            video_urls = normalize_url_list(spec.get("video_url") or spec.get("videoUrl"))

        for url in image_urls:
            children.append({"kind": "image", "image_url": url})
        for url in video_urls:
            child: PostSpec = {"kind": "video", "video_url": url}
            if thumb_offset is not None and len(video_urls) == 1 and not image_urls:
                child["thumb_offset"] = thumb_offset
            children.append(child)

    if not children:
        raise ValueError("Each post must include at least one image or video URL")
    if len(children) > 20:
        raise ValueError("Instagram carousel supports up to 20 media items")

    payload_base: PostSpec = {
        "caption": caption,
        "location_id": location_id,
        "user_tags": user_tags,
    }

    if len(children) == 1:
        child = children[0]
        payload = dict(payload_base)
        payload["kind"] = child["kind"]
        if child["kind"] == "video":
            payload["video_url"] = child["video_url"]
            if child.get("thumb_offset") is not None:
                payload["thumb_offset"] = child["thumb_offset"]
        else:
            payload["image_url"] = child["image_url"]
        return payload

    payload = dict(payload_base)
    payload["kind"] = "carousel"
    normalized_children: List[PostSpec] = []
    for child in children:
        normalized_child: PostSpec = {"kind": child["kind"]}
        if child["kind"] == "video":
            normalized_child["video_url"] = child["video_url"]
            if child.get("thumb_offset") is not None:
                normalized_child["thumb_offset"] = child["thumb_offset"]
        else:
            normalized_child["image_url"] = child["image_url"]
        normalized_children.append(normalized_child)
    payload["children"] = normalized_children
    return payload


def create_media_container(
    config: Dict[str, str],
    spec: PostSpec,
    *,
    is_carousel_item: bool = False,
) -> str:
    data: Dict[str, Any] = {}
    if is_carousel_item:
        data["is_carousel_item"] = True
    else:
        data.update(
            {
                "caption": spec.get("caption"),
                "location_id": spec.get("location_id"),
                "user_tags": spec.get("user_tags"),
            }
        )
    if spec["kind"] == "image":
        data["image_url"] = spec["image_url"]
    else:
        data["media_type"] = "VIDEO"
        data["video_url"] = spec["video_url"]
        if spec.get("thumb_offset") is not None:
            data["thumb_offset"] = spec["thumb_offset"]
    response = graph_post(config, f"/{config['ig_user_id']}/media", data)
    creation_id = response.get("id")
    if not creation_id:
        raise GraphAPIError("Graph API did not return a creation id")
    return creation_id


def wait_for_container_ready(
    config: Dict[str, str],
    creation_id: str,
    poll_interval: float,
    timeout: float,
) -> str:
    deadline = time.time() + timeout
    last_status = "PENDING"
    while True:
        response = graph_get(config, f"/{creation_id}", params={"fields": "status_code,status"})
        status_code = response.get("status_code") or response.get("status")
        if status_code in {"FINISHED", "READY", "EXPIRED", "PUBLISHED"}:
            return status_code
        if status_code == "ERROR":
            raise GraphAPIError(f"Media processing failed for container {creation_id}")
        last_status = status_code or last_status
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for container {creation_id} (last status: {last_status})")
        time.sleep(poll_interval)


def publish_container(config: Dict[str, str], creation_id: str) -> str:
    response = graph_post(
        config,
        f"/{config['ig_user_id']}/media_publish",
        {"creation_id": creation_id},
    )
    media_id = response.get("id")
    if not media_id:
        raise GraphAPIError("Graph API did not return a media id on publish")
    return media_id


def fetch_permalink(config: Dict[str, str], media_id: str) -> Optional[str]:
    try:
        response = graph_get(config, f"/{media_id}", params={"fields": "permalink"})
    except GraphAPIError:
        return None
    return response.get("permalink")


def submit_post(
    config: Dict[str, str],
    spec: PostSpec,
    dry_run: bool,
    poll_interval: float,
    timeout: float,
) -> PostSpec:
    result: PostSpec = {
        "caption": spec.get("caption"),
        "kind": spec["kind"],
    }
    if dry_run:
        result["status"] = "skipped"
        if spec["kind"] == "carousel":
            result["child_count"] = len(spec.get("children", []))
        return result

    if spec["kind"] == "carousel":
        child_ids: List[str] = []
        child_statuses: Dict[str, str] = {}
        for child in spec.get("children", []):
            child_id = create_media_container(config, child, is_carousel_item=True)
            child_ids.append(child_id)
            status_code = wait_for_container_ready(config, child_id, poll_interval, timeout)
            child_statuses[child_id] = status_code
            if status_code not in READY_CONTAINER_STATUSES:
                raise GraphAPIError(
                    f"Carousel media item {child_id} finished with status {status_code}"
                )
        result["child_container_ids"] = child_ids
        result["child_container_statuses"] = child_statuses
        data = {
            "caption": spec.get("caption"),
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "location_id": spec.get("location_id"),
            "user_tags": spec.get("user_tags"),
        }
        response = graph_post(config, f"/{config['ig_user_id']}/media", data)
        creation_id = response.get("id")
        if not creation_id:
            raise GraphAPIError("Graph API did not return a creation id for carousel")
    else:
        creation_id = create_media_container(config, spec)

    result["container_id"] = creation_id
    status_code = wait_for_container_ready(config, creation_id, poll_interval, timeout)
    result["container_status"] = status_code
    if status_code not in READY_CONTAINER_STATUSES:
        raise GraphAPIError(
            f"Media container {creation_id} finished with status {status_code}"
        )

    media_id = publish_container(config, creation_id)
    result["status"] = "posted"
    result["media_id"] = media_id
    permalink = fetch_permalink(config, media_id)
    if permalink:
        result["permalink"] = permalink
    return result


def write_results(results: List[PostSpec], output_path: Optional[str]) -> Optional[Path]:
    if not results:
        return None
    target = Path(output_path).expanduser() if output_path else None
    if not target:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        target = Path(__file__).resolve().with_name(f"instagram_post_results_{timestamp}.json")
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
    if not image_urls and not video_urls:
        raise ValueError(
            "Provide at least one --image-url or --video-url when not using --posts-file"
        )
    spec: PostSpec = {
        "caption": args.caption,
        "image_urls": image_urls,
        "video_urls": video_urls,
        "thumb_offset": args.thumb_offset,
        "location_id": args.location_id,
        "user_tags": args.user_tags,
    }
    return [spec]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload Instagram posts via the Graph API.")
    parser.add_argument("--credentials", help="Path to credentials JSON file")
    parser.add_argument("--posts-file", help="JSON file describing posts to upload")
    parser.add_argument("--caption", help="Caption text for single post mode")
    parser.add_argument(
        "--image-url",
        dest="image_urls",
        action="append",
        help="Public image URL (repeat for multiple images)",
    )
    parser.add_argument(
        "--video-url",
        dest="video_urls",
        action="append",
        help="Public video URL (repeat for multiple videos)",
    )
    parser.add_argument("--thumb-offset", type=float, help="Seconds into video for thumbnail selection")
    parser.add_argument("--location-id", help="Instagram location ID")
    parser.add_argument("--user-tags", help="JSON describing user tags")
    parser.add_argument("--graph-version", help="Graph API version (defaults to v19.0)")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between status checks")
    parser.add_argument("--timeout", type=float, default=300.0, help="Maximum seconds to wait for processing")
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
        "ig_user_id": creds["ig_user_id"],
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
            outcome = submit_post(
                config,
                spec,
                dry_run=args.dry_run,
                poll_interval=args.poll_interval,
                timeout=args.timeout,
            )
        except Exception as exc:
            outcome = {
                "caption": spec.get("caption"),
                "kind": spec["kind"],
                "status": "failed",
                "error": str(exc),
            }
        results.append(outcome)
        status = outcome.get("status", "unknown")
        permalink = outcome.get("permalink") or outcome.get("error") or ""
        preview = (spec.get("caption") or "[no caption]").replace("\n", " ")[:60]
        print(f"[{status.upper()}] {preview} {permalink}")

    saved_path = write_results(results, args.results_file)
    if saved_path:
        print(f"Results saved to {saved_path}")
    if args.dry_run:
        print("Dry run complete. No posts were published.")


if __name__ == "__main__":
    main()
