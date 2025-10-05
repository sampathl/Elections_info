import argparse
import json
from typing import Optional, Sequence

from social_media_connectors.youtube_video_upload_service import (
    YouTubeUploadLimitError,
    upload_video_and_add_to_playlist,
    upload_video_with_quota_handling,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a YouTube video and optionally add it to a playlist.",
    )
    parser.add_argument("--file", required=True, help="Path to the video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--category-id", default="22", help="YouTube video category ID")
    parser.add_argument(
        "--privacy-status",
        default="private",
        choices=["private", "public", "unlisted"],
        help="Video privacy status",
    )
    parser.add_argument("--tags", nargs="*", help="Optional space separated list of tags")
    parser.add_argument("--playlist-id", help="If provided, add the uploaded video to this playlist")
    parser.add_argument("--playlist-position", type=int, help="Optional position in the playlist")
    parser.add_argument(
        "--client-secrets",
        default="credentials.json",
        help="Path to OAuth client secrets JSON",
    )
    parser.add_argument(
        "--token-file",
        default="token.json",
        help="Path to stored OAuth token JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tags: Optional[Sequence[str]] = args.tags

    try:
        if args.playlist_id:
            result = upload_video_and_add_to_playlist(
                video_path=args.file,
                title=args.title,
                playlist_id=args.playlist_id,
                description=args.description,
                category_id=args.category_id,
                privacy_status=args.privacy_status,
                tags=tags,
                playlist_position=args.playlist_position,
                client_secrets_file=args.client_secrets,
                token_file=args.token_file,
            )
        else:
            video_id = upload_video_with_quota_handling(
                video_path=args.file,
                title=args.title,
                description=args.description,
                category_id=args.category_id,
                privacy_status=args.privacy_status,
                tags=tags,
                client_secrets_file=args.client_secrets,
                token_file=args.token_file,
            )
            result = {"upload": {"video_id": video_id}}
    except YouTubeUploadLimitError as exc:
        raise SystemExit(f"Upload failed due to quota limits: {exc}")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
