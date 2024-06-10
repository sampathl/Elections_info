from generate_videos.scripts.constants import STATIC_FOLDER_PATH
import random


def fetch_background_image_locations():

    background_image_folder_path=STATIC_FOLDER_PATH+"images/image_set/image_colors/"
    background_color_folder_path=['yellow/', 'green/','blue/']
    background_images_names= {'name': 'name.png', 
                        'party':'name.png',
                        'constituency':'victory.png',
                        'age':'victory.png', 
                        'education':'education.png',
                        'criminal_cases':'cases.png',
                        'assets':'assets.png',
                        'liabilities':'assets.png'}

    color=random.choice(background_color_folder_path)
    return {key:background_image_folder_path+color+background_images_names[key] for key in background_images_names.keys()}

def convert_timings(audio_timings):
    timings={}
    for i in audio_timings:
        if 'markName' in i:
            timings[i['markName']]=i['timeSeconds']
    return timings