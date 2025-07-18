from googleapiclient.discovery import build
from google.oauth2 import service_account

# Replace with your service account file and channel ID
SERVICE_ACCOUNT_FILE = 'path/to/your/service-account.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
CHANNEL_ID = 'YOUR_CHANNEL_ID'

# List of playlist titles to create
playlist_titles = [
    "Playlist 1",
    "Playlist 2",
    "Playlist 3"
]

def get_authenticated_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('youtube', 'v3', credentials=credentials)

def create_playlist(youtube, title, description=""):
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description
            },
            "status": {
                "privacyStatus": "public"
            }
        }
    )
    response = request.execute()
    print(f"Created playlist: {title} (ID: {response['id']})")
    return response['id']

def main():
    youtube = get_authenticated_service()
    for title in playlist_titles:
        create_playlist(youtube, title)

if __name__ == "__main__":
    main()
