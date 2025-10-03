
GCP_KEY="AIzaSyA9zk7xH_5b06s3Hda8BfVdGpbEkiYNeGc"
STATIC_FOLDER_PATH = "/Users/saml16/projects/Elections_info/static/"
DEBUG_TEXT="**************************"

TEXT_CLIP_PROPS={'align':'North', 'font':'Futura-Bold', 'color':'White', 'method':'caption', 'stroke_color':'GhostWhite', 'stroke_width':1}




working_dir= STATIC_FOLDER_PATH

PROFILE_IMAGE_PATH=STATIC_FOLDER_PATH+ "lok_sabha_2024/phase_1/images/"
PARTY_IMAGE_PATH=STATIC_FOLDER_PATH+ "Party/images/"
VIDEO_LOCATION = STATIC_FOLDER_PATH+ "lok_sabha_2024/phase_1/videos/"
AUDIO_CLIP_LOCATION=STATIC_FOLDER_PATH+ "lok_sabha_2024/phase_1/audio/"
DISCLAIMER_IMAGE_PATH=STATIC_FOLDER_PATH+ "images/notice.png"
BACKGROUND_AUDIO_PATH= STATIC_FOLDER_PATH+"background/vm_f.mp3"



GCP_VOICE_OPTIONS=[  {"name" : "en-IN-Neural2-A",  "pitch": -4.4,"speakingRate": 0.93}, 
    { "name": "en-IN-Neural2-A", "pitch": 0 ,"speakingRate": 1},
    { "name": "en-IN-Neural2-A", "pitch": 2 ,"speakingRate": 1},
    {"name" : "en-IN-Neural2-D", "pitch": -3.6,"speakingRate": 0.93},
    {"name" : "en-IN-Neural2-D", "pitch": 0 ,"speakingRate": 1},
    { "name" : "en-IN-Neural2-D", "pitch": 3.2 ,"speakingRate": 1.0}, 
    {"name" : "en-IN-Neural2-B", "pitch": -5.6,"speakingRate": 0.89},
    { "name" : "en-IN-Neural2-B","pitch": 0 ,"speakingRate": 1},
    {"name" : "en-IN-Neural2-B", "pitch": 3.2 ,"speakingRate": 0.93},
    {"name" : "en-IN-Neural2-C", "pitch": -14.0,"speakingRate": 1.0},
    {"name" : "en-IN-Neural2-C", "pitch": 0 ,"speakingRate": 1}]

