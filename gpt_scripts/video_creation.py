from moviepy.editor import ImageClip, AudioFileClip

def create_video(image_file, audio_file, output_file):
    image_clip = ImageClip(image_file)
    audio_clip = AudioFileClip(audio_file)

    # Set the duration of the image clip to the duration of the audio clip
    video_clip = image_clip.set_duration(audio_clip.duration)

    # Set the audio of the video clip as the audio clip
    final_clip = video_clip.set_audio(audio_clip)

    final_clip.write_videofile(output_file, fps=24)

# Example usage
create_video("nature.jpg", "output.mp3", "final_video.mp4")
