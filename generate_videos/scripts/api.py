

# generate audio
import base64
import io
import logging
import random

import requests

from generate_videos.scripts.constants import DEBUG_TEXT, GCP_KEY, GCP_VOICE_OPTIONS
from generate_videos.scripts.helper_functions import convert_timings


def generate_audio_from_text(request_string, output_location, language='en-US'):
    # Set up the API endpoint and parameters
    api_url = 'https://texttospeech.googleapis.com/v1beta1/text:synthesize'
    api_key =  GCP_KEY
    headers = {'Content-Type': 'application/json'}
    voice=random.choice(GCP_VOICE_OPTIONS)
    data = {
        'input': {'ssml': str(request_string)},
        "voice": {"languageCode": "en-IN","name": voice.get("name","en-IN-Neural2-A")},
        'audioConfig': {'audioEncoding': 'MP3', 
                        "pitch": voice.get("pitch",0),
                        "speakingRate": voice.get("speakingRate",1), 
                        "effectsProfileId": ["handset-class-device"]},
        "enableTimePointing": ["SSML_MARK"]
    }
    logging.debug(DEBUG_TEXT+"audio fetched")
    logging.debug("fetching audio", request_string)
    
    # Requesting TTS API
    response = requests.post(f'{api_url}?key={api_key}', headers=headers, json=data)
    
    response.raise_for_status()
    response = response.json()
    # Decoding auding file
    audio_data = base64.b64decode(response["audioContent"])
    audio_file = io.BytesIO(audio_data)
    

    # Save file
    with open(str(output_location) + ".mp3", 'wb') as out_file:
        out_file.write(audio_file.read())
    
    logging.debug(DEBUG_TEXT+"audio timepoints fetched")
    logging.debug(response["timepoints"])
    #return  marks dict.
    return convert_timings(response["timepoints"])