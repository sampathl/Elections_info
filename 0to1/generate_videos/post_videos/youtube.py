import os
import pandas as pd

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors

# Set up the OAuth 2.0 credentials
scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Replace 'YOUR_CLIENT_SECRET_FILE.json' with your client secret file
flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
    '/Users/saml16/projects/Elections_info/client_secret_lok_sabha.json', scopes)
credentials = flow.run_local_server(port=0)

# Create a YouTube Data API client
youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=credentials)


# Assuming you have a pandas DataFrame called 'df' with columns 'title' and 'description'

# Iterate over the rows of the DataFrame
for index, row in [{'title': 'test1', 'description': 'description1'}, {'title': 'test2', 'description': 'description2'}]:
    # Create a new playlist
    request = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": row['title'],
                "description": row['description']
            },
            "status": {
                "privacyStatus": "private"
            }
        }
    )
    response = request.execute()

    # Print the playlist ID
    print("Playlist created! ID:", response['id'])