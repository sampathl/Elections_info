
import logging
import os
from generate_videos.scripts.api import generate_audio_from_text
from generate_videos.scripts.constants import VIDEO_LOCATION
from generate_videos.scripts.generate_text_for_audio import generate_candidate_audio_strings
from generate_videos.scripts.generate_text_for_fonts import generate_candidate_video_text
from generate_videos.scripts.generate_video import generate_video
import pandas as pd
import time
import json

def main():
    combined_file_location = '/Users/saml16/projects/Elections_info/static/lok_sabha_2024/phase_1/combined_candidates_with_party1.csv'
    audio_output_folder_location = '/Users/saml16/projects/Elections_info/static/lok_sabha_2024/phase_1/audio/'
    video_location='/Users/saml16/projects/Elections_info/static/lok_sabha_2024/phase_1/video/'
    
    start_time = time.time()
    combined = pd.read_csv(combined_file_location)  
    test= combined[1000:1700]
    new_audio_timings={}

    for row in test.to_dict(orient='records'):
        try:
            # generate text ssml.
            audio_text_dict=generate_candidate_audio_strings(row)
            logging.debug(str(audio_text_dict))

            audio_text= "".join(['<speak>',audio_text_dict.get('name',""), 
                                    audio_text_dict.get('party',""),
                                    audio_text_dict.get('constituency',""),
                                    audio_text_dict.get('age',""),
                                    audio_text_dict.get('education',""), 
                                    audio_text_dict.get('criminal_cases',""),
                                    ", has" if audio_text_dict.get('assets',"") else "" ,
                                    audio_text_dict.get('assets',""),
                                    "and" if audio_text_dict.get('liabilities',"") else "", 
                                    audio_text_dict.get('liabilities',"") , '</speak>'])

            audio_timings=generate_audio_from_text(audio_text,audio_output_folder_location+str(row['nem_candidate_id']))
            audio_timings['audio_text']=audio_text
            new_audio_timings[row['nem_candidate_id']]=audio_timings

            # create videos 
            video_text=generate_candidate_video_text(row)

            generate_video(audio_timings, video_text, row.get('nem_candidate_id',None), int(row.get('nem_party_id') or 0) , video_location=video_location)

        except Exception as e:
            logging.error(f"Error processing row with nem_candidate_id: {row['nem_candidate_id']}. Error: {str(e)}")
            # Write the nem_candidate_id to a separate file for error handling
            with open('/Users/saml16/projects/Elections_info/static/lok_sabha_2024/phase_1/error_handling.txt', 'a') as file:
                file.write(str(row['nem_candidate_id']) + '\n')

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Total time taken for generating videos {elapsed_time}")
    
    
    # Check if the audio_timings_file already exists
    if os.path.exists(audio_output_folder_location+'audio_timings_file.json'):
        # Load the existing audio_timings_file
        with open(audio_output_folder_location+'audio_timings_file.json', 'r') as file:
            audio_timings_file = json.load(file)
    else:
        # Create a new audio_timings_file
        audio_timings_file = {}

    # Append or update the audio_timings_file with the new timings
    audio_timings_file.update(new_audio_timings  )

    # Save the updated audio_timings_file
    with open(audio_output_folder_location+'audio_timings_file.json', 'w') as file:
        json.dump(audio_timings_file, file)



if __name__ == '__main__':
    main()