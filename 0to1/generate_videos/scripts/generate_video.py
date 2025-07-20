from moviepy.editor import *

from generate_videos.scripts.constants import AUDIO_CLIP_LOCATION, BACKGROUND_AUDIO_PATH, DISCLAIMER_IMAGE_PATH, PARTY_IMAGE_PATH, PROFILE_IMAGE_PATH, VIDEO_LOCATION
from generate_videos.scripts.generate_videos_part import generate_video_part
from generate_videos.scripts.helper_functions import fetch_background_image_locations


def generate_video( audio_timings, video_text, nem_id, party_id, video_location=VIDEO_LOCATION):
    background_images=fetch_background_image_locations()
    
    if audio_timings.get('name',None):
        videos=[]
        
        # Name
        profile_image=PROFILE_IMAGE_PATH+str(nem_id)+".jpg"
        name_v = generate_video_part(background_images['name'],{'name':'name', 'content':video_text['name']},audio_timings['name'], center_image=profile_image, profile_picture=None, party_picture=None)
        videos.append(name_v)
    else:
        return 
    
    #text = TextClip("Akbaruddin Owaisi Akbaruddin Owaisi Akbaruddin Owaisi".upper(), align='North', font='Bodoni-72-Oldstyle-Bold', fontsize=72, font='Bodoni-72-Oldstyle-Bold', color='goldenrod1', stroke_color='GhostWhite',  stroke_width=1, method='caption').set_position('center').set_duration(2.451604127883911)
    
    
    if audio_timings.get('party',None):
        # Party
        party_duration=audio_timings['party']- audio_timings['name']
        party_image=PARTY_IMAGE_PATH+str(party_id)+".png"
        party_v = generate_video_part(background_images['party'],{'name':'party', 'content':video_text['party']},party_duration, center_image=party_image, profile_picture=profile_image, party_picture=None)
        videos.append(party_v)
    
    
    
    if audio_timings.get('constituency',None) and audio_timings.get('party',None):
        # constituency 
        ######## change this if no constitunecy

        constituency_duration=audio_timings['constituency']- audio_timings['party']
        constituency_v = generate_video_part(background_images['party'],{'name':'constituency', 'content':video_text['constituency']},constituency_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        videos.append(constituency_v)
    
    if audio_timings.get('age',None) and audio_timings.get('constituency',None):
        # Age
        age_duration=audio_timings['age']- audio_timings['constituency']
        age_v = generate_video_part(background_images['age'],{'name':'age', 'content':video_text['age']},age_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        videos.append(age_v)
    
    if audio_timings.get('education',None) and audio_timings.get('age',None):
    
        # Education
        education_duration=audio_timings['education']- audio_timings['age']
        education_v = generate_video_part(background_images['education'],{'name':'education', 'content':video_text['education']},education_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        videos.append(education_v)

    
    if audio_timings.get('criminal_cases',None) and audio_timings.get('education',None):
    
        # Criminal_cases
        cases_duration=audio_timings['criminal_cases']- audio_timings['education']
        cases_v = generate_video_part(background_images['criminal_cases'],{'name':'Cases', 'content':video_text['criminal_cases']},cases_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        videos.append(cases_v)
    
    
    if audio_timings.get('assets',None) and audio_timings.get('criminal_cases',None):
        # Assets
        assets_duration=audio_timings['assets']- audio_timings['criminal_cases']
        assets_v = generate_video_part(background_images['assets'],{'name':'assets', 'content':video_text['assets']},assets_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        videos.append(assets_v)
    
    
    
    if audio_timings.get('liabilities',None) and audio_timings.get('assets',None):
        # Liabilities
        liabilities_duration=audio_timings['liabilities']- audio_timings['assets']
        liabilities_v = generate_video_part(background_images['liabilities'],{'name':'liabilities', 'content':video_text['liabilities']},liabilities_duration, center_image=None, profile_picture=profile_image, party_picture=party_image)
        print("liabilites,,",end="\t")
        videos.append(liabilities_v)
    
    
    # Combine video
    final_clip = concatenate_videoclips(videos)
    
    
    # Load the audio file
    audio = AudioFileClip(AUDIO_CLIP_LOCATION+str(nem_id)+".mp3")

    
    if DISCLAIMER_IMAGE_PATH and os.path.isfile(DISCLAIMER_IMAGE_PATH):
        disclaimer_clip= ImageClip(DISCLAIMER_IMAGE_PATH, duration=2)
        final_clip = concatenate_videoclips([final_clip,disclaimer_clip])
    
    audio_background = AudioFileClip(BACKGROUND_AUDIO_PATH).set_duration(final_clip.duration).volumex(0.05)
    final_audio = CompositeAudioClip([audio, audio_background])

    
    # Set the audio of the video clip
    video = final_clip.set_audio(final_audio)

    video.write_videofile(video_location+str(nem_id)+".mp4", fps=60)
    audio.close()
    
    return video
