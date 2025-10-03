import os
import facebook

def upload_videos(folder_path, comments):
    # Create a Facebook Graph API object
    access_token = 'YOUR_ACCESS_TOKEN'
    graph = facebook.GraphAPI(access_token)

    # Iterate over each video file in the folder
    for file, comment in comments.items():
        # Get the full path of the file
        file_path = os.path.join(folder_path, file)

        # Open the video file
        with open(file_path, 'rb') as video_file:
            # Upload the video using the Graph API
            response = graph.put_video(video_file, title=comment)

            # Get the video ID from the response
            video_id = response['id']
            print(f"Video uploaded successfully. ID: {video_id}")

# Specify the folder path and comments
folder_path = '/Users/saml16/projects/Elections_info/static/Loksabha2019/Winners/videos/'
comments = {
    'video1.mp4': 'This is the first video',
    'video2.mp4': 'Check out this amazing video',
    'video3.mp4': 'Throwback to a fun day'
}

# Call the function to upload the videos
upload_videos(folder_path, comments)
