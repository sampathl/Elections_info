import argparse
import os
from typing import Dict, List, Optional, Sequence, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Use --https://support.google.com/youtube/contact/yt_api_form

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def get_credentials(client_secrets_file: str, token_file: str = "token.json") -> Credentials:
    """Retrieve stored OAuth credentials or start a new OAuth flow."""
    creds: Optional[Credentials] = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            try:
                creds = flow.run_local_server(port=8080, access_type="offline")
            except Exception:
                try:
                    creds = flow.run_local_server(port=0, access_type="offline")
                except Exception:
                    auth_url, _ = flow.authorization_url(prompt="consent")
                    print(f"Please go to this URL: {auth_url}")
                    code = input("Enter the authorization code: ")
                    flow.fetch_token(code=code)
                    creds = flow.credentials
        with open(token_file, "w") as token_handle:
            token_handle.write(creds.to_json())
    return creds


def build_youtube_service(client_secrets_file: str = "credentials.json",
                          token_file: str = "token.json"):
    """Return an authenticated YouTube Data API client."""
    creds = get_credentials(client_secrets_file, token_file)
    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str,
                 title: str,
                 description: str = "",
                 category_id: str = "22",
                 privacy_status: str = "private",
                 tags: Optional[Sequence[str]] = None,
                 client_secrets_file: str = "credentials.json",
                 token_file: str = "token.json") -> str:
    """Upload a video and return the created video's ID."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = build_youtube_service(client_secrets_file, token_file)
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }
    if tags:
        body["snippet"]["tags"] = list(tags)

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("Failed to retrieve video ID from upload response")
    return video_id


def add_video_to_playlist(playlist_id: str,
                          video_id: str,
                          position: Optional[int] = None,
                          client_secrets_file: str = "credentials.json",
                          token_file: str = "token.json",
                          youtube=None) -> str:
    """Insert an existing video into a playlist and return the playlist item ID."""
    service = youtube or build_youtube_service(client_secrets_file, token_file)

    snippet = {
        "playlistId": playlist_id,
        "resourceId": {
            "kind": "youtube#video",
            "videoId": video_id,
        },
    }
    if position is not None:
        snippet["position"] = position

    response = service.playlistItems().insert(part="snippet", body={"snippet": snippet}).execute()
    playlist_item_id = response.get("id")
    if not playlist_item_id:
        raise RuntimeError("Failed to retrieve playlist item ID from response")
    return playlist_item_id


def create_playlist(title: str,
                    description: str = "",
                    privacy: str = "private",
                    youtube=None,
                    client_secrets_file: str = "credentials.json",
                    token_file: str = "token.json") -> str:
    """Create a playlist and return its ID."""
    service = youtube or build_youtube_service(client_secrets_file, token_file)
    body = {
        "snippet": {
            "title": title,
            "description": description,
        },
        "status": {
            "privacyStatus": privacy,
        },
    }
    response = service.playlists().insert(part="snippet,status", body=body).execute()
    playlist_id = response.get("id")
    if not playlist_id:
        raise RuntimeError("Failed to retrieve playlist ID from response")
    return playlist_id


def parse_constituency_file(file_path: str, start_from: str = None) -> Tuple[List[str], List[str]]:
    """Parse the constituency file and extract names and Wikipedia links."""
    titles: List[str] = []
    descriptions: List[str] = []
    found_start = start_from is None

    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()
                if line and " - " in line:
                    parts = line.split(" - ", 1)
                    if len(parts) != 2:
                        continue
                    constituency_name = parts[0].strip()
                    wiki_link = parts[1].strip()

                    if not found_start:
                        if constituency_name.lower() == start_from.lower():
                            print(f"Found starting point: {constituency_name}")
                            found_start = True
                            continue
                        continue

                    titles.append(f"{constituency_name} Constituency")
                    descriptions.append(
                        f"Information about {constituency_name} Assembly constituency in Bihar. Wikipedia: {wiki_link}"
                    )
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
    except Exception as exc:  # noqa: BLE001
        print(f"Error reading file: {exc}")

    if start_from and not found_start:
        print(f"Warning: Starting constituency '{start_from}' not found in file")

    return titles, descriptions


def create_playlists(titles: List[str],
                     client_secrets_file: str = "credentials.json",
                     token_file: str = "token.json",
                     privacy: str = "private",
                     description: str = "",
                     descriptions: Optional[List[str]] = None) -> List[Dict]:
    """Create multiple playlists and return metadata for each result."""
    youtube = build_youtube_service(client_secrets_file, token_file)
    created: List[Dict] = []

    for index, title in enumerate(titles):
        playlist_description = descriptions[index] if descriptions and index < len(descriptions) else description
        try:
            playlist_id = create_playlist(
                title=title,
                description=playlist_description,
                privacy=privacy,
                youtube=youtube,
            )
            created.append({"title": title, "id": playlist_id, "description": playlist_description})
        except HttpError as error:
            created.append({"title": title, "error": str(error)})
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube helper script")
    parser.add_argument("--client-secrets", default="credentials.json", help="Path to OAuth client secrets JSON")
    parser.add_argument("--token-file", default="token.json", help="Path to stored OAuth token JSON")

    subparsers = parser.add_subparsers(dest="command")

    upload_parser = subparsers.add_parser("upload", help="Upload a video and return its ID")
    upload_parser.add_argument("--file", required=True, help="Path to the video file")
    upload_parser.add_argument("--title", required=True, help="Video title")
    upload_parser.add_argument("--description", default="", help="Video description")
    upload_parser.add_argument("--category-id", default="22", help="YouTube video category ID")
    upload_parser.add_argument(
        "--privacy-status",
        default="private",
        choices=["private", "public", "unlisted"],
        help="Video privacy status",
    )
    upload_parser.add_argument("--tags", nargs="*", help="Optional space separated list of tags")

    add_parser = subparsers.add_parser("add-to-playlist", help="Add a video to a playlist")
    add_parser.add_argument("--playlist-id", required=True, help="Target playlist ID")
    add_parser.add_argument("--video-id", required=True, help="Video ID to add")
    add_parser.add_argument("--position", type=int, help="Optional position index within the playlist")

    create_parser = subparsers.add_parser("create-playlist", help="Create a playlist and return its ID")
    create_parser.add_argument("--title", required=True, help="Playlist title")
    create_parser.add_argument("--description", default="", help="Playlist description")
    create_parser.add_argument(
        "--privacy-status",
        default="private",
        choices=["private", "public", "unlisted"],
        help="Playlist privacy status",
    )

    args = parser.parse_args()
    if args.command == "upload":
        video_id = upload_video(
            video_path=args.file,
            title=args.title,
            description=args.description,
            category_id=args.category_id,
            privacy_status=args.privacy_status,
            tags=args.tags,
            client_secrets_file=args.client_secrets,
            token_file=args.token_file,
        )
        print(video_id)
    elif args.command == "add-to-playlist":
        playlist_item_id = add_video_to_playlist(
            playlist_id=args.playlist_id,
            video_id=args.video_id,
            position=args.position,
            client_secrets_file=args.client_secrets,
            token_file=args.token_file,
        )
        print(playlist_item_id)
    elif args.command == "create-playlist":
        playlist_id = create_playlist(
            title=args.title,
            description=args.description,
            privacy=args.privacy_status,
            client_secrets_file=args.client_secrets,
            token_file=args.token_file,
        )
        print(playlist_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
