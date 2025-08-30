import os
import json
from typing import List, Dict
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_credentials(client_secrets_file: str, token_file: str = "token.json") -> Credentials:
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            # Try different approaches to handle redirect URI issues
            try:
                # First try with a fixed port that might work with your OAuth config
                creds = flow.run_local_server(port=8080, access_type='offline')
            except Exception as e:
                print(f"Port 8080 failed: {e}")
                try:
                    # Try with no specific port (let system choose)
                    creds = flow.run_local_server(port=0, access_type='offline')
                except Exception as e2:
                    print(f"Dynamic port failed: {e2}")
                    # Manual flow as fallback
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print(f'Please go to this URL: {auth_url}')
                    code = input('Enter the authorization code: ')
                    flow.fetch_token(code=code)
                    creds = flow.credentials
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return creds

def parse_constituency_file(file_path: str, start_from: str = None) -> tuple[List[str], List[str]]:
    """
    Parse the constituency file and extract names and Wikipedia links.
    
    Args:
        file_path: Path to the text file containing constituency data
        start_from: Constituency name to start from (skip all before this)
        
    Returns:
        Tuple of (titles, descriptions) lists
    """
    titles = []
    descriptions = []
    found_start = start_from is None  # If no start_from specified, start immediately
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and ' - ' in line:
                    # Split by ' - ' to separate name and link
                    parts = line.split(' - ', 1)  # Split only on first occurrence
                    if len(parts) == 2:
                        constituency_name = parts[0].strip()
                        wiki_link = parts[1].strip()
                        
                        # Check if we've reached the starting point
                        if not found_start:
                            if constituency_name.lower() == start_from.lower():
                                print(f"Found starting point: {constituency_name}")
                                found_start = True
                                # Skip the starting constituency itself, start from the next one
                                continue
                            else:
                                # Skip this constituency
                                continue
                        
                        titles.append(f"{constituency_name} Constituency")
                        descriptions.append(f"Information about {constituency_name} Assembly constituency in Bihar. Wikipedia: {wiki_link}")
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
    except Exception as e:
        print(f"Error reading file: {e}")
    
    if start_from and not found_start:
        print(f"Warning: Starting constituency '{start_from}' not found in file")
    
    return titles, descriptions

def create_playlists(titles: List[str],
                     client_secrets_file: str = "credentials.json",
                     token_file: str = "token.json",
                     privacy: str = "private",
                     description: str = "",
                     descriptions: List[str] = None) -> List[Dict]:
    """
    Create playlists on the authorized YouTube account.
    Returns a list of dicts with created playlist IDs and titles.
    
    Args:
        titles: List of playlist titles
        client_secrets_file: Path to OAuth client secrets file
        token_file: Path to store credentials
        privacy: "private", "public", or "unlisted"
        description: Single description for all playlists (ignored if descriptions is provided)
        descriptions: List of descriptions (one per playlist). If provided, overrides description.
    """
    creds = get_credentials(client_secrets_file, token_file)
    youtube = build("youtube", "v3", credentials=creds)
    created = []
    
    for i, title in enumerate(titles):
        # Use individual description if available, otherwise use the single description
        playlist_description = descriptions[i] if descriptions and i < len(descriptions) else description
        
        body = {
            "snippet": {
                "title": title,
                "description": playlist_description
            },
            "status": {
                "privacyStatus": privacy  # "private", "public", or "unlisted"
            }
        }
        try:
            resp = youtube.playlists().insert(part="snippet,status", body=body).execute()
            created.append({"title": title, "id": resp.get("id"), "description": playlist_description})
        except HttpError as e:
            # continue on error and include error message
            created.append({"title": title, "error": str(e)})
    return created

if __name__ == "__main__":
    # Path to your constituency file
    constituency_file = "/Users/saml16/projects/Elections_info/static/bihar_constituency.txt"
    client_secrets = "/Users/saml16/Desktop/Keys/youtube_election.json"
    
    # Start from the constituency after Sahebganj (due to API limit reached)
    start_from_constituency = "Sahebganj"
    
    # Parse the constituency file to get titles and descriptions, starting from specified constituency
    print(f"Reading constituency data starting after '{start_from_constituency}'...")
    titles, descriptions = parse_constituency_file(constituency_file, start_from=start_from_constituency)
    
    print(f"Found {len(titles)} constituencies to process (starting after {start_from_constituency})")
    
    if not titles:
        print("No constituency data found after the specified starting point. Please check the file path and format.")
        exit(1)
    
    # Show first few examples
    print(f"\nFirst 5 constituencies (starting after {start_from_constituency}):")
    for i in range(min(5, len(titles))):
        print(f"  {i+1}. {titles[i]}")
        print(f"     Description: {descriptions[i][:100]}...")
    
    # Ask for confirmation before creating playlists
    response = input(f"\nDo you want to create {len(titles)} playlists? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        exit(0)
    
    print("\nCreating playlists...")
    results = create_playlists(
        titles=titles, 
        client_secrets_file=client_secrets,
        descriptions=descriptions,
        privacy="private"  # Change to "public" or "unlisted" if needed
    )
    
    # Print results
    print(f"\nPlaylist creation completed!")
    successful = [r for r in results if 'id' in r]
    failed = [r for r in results if 'error' in r]
    
    print(f"Successfully created: {len(successful)} playlists")
    print(f"Failed: {len(failed)} playlists")
    
    if failed:
        print("\nFailed playlists:")
        for result in failed:
            print(f"  - {result['title']}: {result['error']}")
    
    # Save results to file with timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"playlist_creation_results_after_{start_from_constituency}_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_file}")