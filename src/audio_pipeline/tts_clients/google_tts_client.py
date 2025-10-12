import os
import random
import argparse
from typing import Optional, List, Dict, Any, Tuple
from google.cloud import texttospeech_v1beta1 as  texttospeech
from google.protobuf.json_format import MessageToDict
from itertools import cycle

# --- Configuration for Indian Language Codes and Voice Cycling ---

""" ### importatant, there s is a issue with SynthesizeSpeechResponse: DESCRIPTOR  in google tts, so use the tts environment to run the audio generation piepline."""

# Dictionary to map two-letter language codes to their Google TTS BCP-47 codes (region-specific)
# Focusing on Indian languages as requested, using 'IN' region.
LANGUAGE_MAP: Dict[str, str] = {
    "hi": "hi-IN",  # Hindi (India)
    "bn": "bn-IN",  # Bengali (India)
    "te": "te-IN",  # Telugu (India)
    "mr": "mr-IN",  # Marathi (India)
    "ta": "ta-IN",  # Tamil (India)
    "gu": "gu-IN",  # Gujarati (India)
    "kn": "kn-IN",  # Kannada (India)
    "ml": "ml-IN",  # Malayalam (India)
    # Common non-Indian language for completeness/example:
    "en": "en-IN",  # English (India)
}

# Default list of Chirp 3: HD voices for the cycling mechanism.
# Note: Chirp 3 HD voices are often language-specific. For this script, 
# we'll use a common convention of appending the name (like 'Aoede')
# to the language code to form the full voice name, e.g., 'en-US-Chirp3-HD-Aoede'.
# The user-provided list in `voice_options` is expected to contain *only* the
# base voice names (e.g., ['Aoede', 'Charon']).
DEFAULT_CHIRP3_VOICES: List[str] = [
    "Aoede",      # Female, Breezy
    "Charon",     # Male, Informative
    "Puck",       # Male, Upbeat
    "Kore",       # Female, Firm
    "Fenrir",     # Male, Excitable
]

# Create a cycler object for random but cycling voice selection
# This holds the state and ensures voices are used one after the other before repeating.
voice_cycler = cycle(random.sample(DEFAULT_CHIRP3_VOICES, len(DEFAULT_CHIRP3_VOICES)))

# --- Client Function ---

def synthesize_audio_with_chirp3(
    text_or_ssml: str,
    language_code_2letter: str,
    output_filepath: str,
    voice_options: Optional[List[str]] = None,
    audio_encoding: texttospeech.AudioEncoding = texttospeech.AudioEncoding.MP3,
) -> Tuple[Dict[str, Any], str]:
    """
    Sends a request to Google TTS using Chirp 3 HD voices, saves the audio file,
    and returns the response without the audio content.

    Args:
        text_or_ssml: The text or SSML to synthesize.
        language_code_2letter: A two-letter language code (e.g., 'hi', 'en').
        output_filepath: The path to save the generated audio file (e.g., 'output.mp3').
        voice_options: Optional list of Chirp 3 HD voice names (e.g., ['Aoede', 'Charon']).
                       If provided, it updates the cycling mechanism.
        audio_encoding: The desired audio encoding (e.g., MP3).

    Returns:
        A tuple containing:
        - The API response as a dictionary (excluding the audio_content).
        - The full voice name used for the request.
    
    Raises:
        ValueError: If the language code is not supported or configuration is missing.
    """
    global voice_cycler
    
    # 1. Map 2-letter code to BCP-47 Google TTS code (e.g., 'hi' -> 'hi-IN')
    lang_code_bcp47 = LANGUAGE_MAP.get(language_code_2letter.lower())
    if not lang_code_bcp47:
        raise ValueError(
            f"Unsupported language code: {language_code_2letter}. "
            f"Supported codes are: {', '.join(LANGUAGE_MAP.keys())}"
        )

    # 2. Update and cycle the voice selection
    if voice_options:
        # Create a new cycler based on the provided, randomized list
        voice_cycler = cycle(random.sample(voice_options, len(voice_options)))
    
    # Get the next voice name from the cycler
    base_voice_name = next(voice_cycler)
    
    # Construct the full Chirp 3 HD voice name
    # The convention is generally: {language_code}-Chirp3-HD-{base_voice_name}
    full_voice_name = f"{lang_code_bcp47}-Chirp3-HD-{base_voice_name}"
    
    # 3. Initialize the client
    client = texttospeech.TextToSpeechClient()

    # 4. Set the text input (check for SSML structure)
    if text_or_ssml.strip().startswith('<speak'):
        print(text_or_ssml)
        synthesis_input = texttospeech.SynthesisInput(ssml=text_or_ssml)
    else:
        synthesis_input = texttospeech.SynthesisInput(text=text_or_ssml)

    # 5. Build the voice request
    voice = texttospeech.VoiceSelectionParams(
        language_code=lang_code_bcp47,
        name=full_voice_name,
    )

    # 6. Select the type of audio file to be returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=audio_encoding,
    )

    req = texttospeech.SynthesizeSpeechRequest(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
        enable_time_pointing=[texttospeech.SynthesizeSpeechRequest.TimepointType.SSML_MARK],
    )

    # 7. Perform the text-to-speech request
    print(f"Synthesizing audio using voice: {full_voice_name}...")
    response = client.synthesize_speech( req )
    print("Synthesis complete.")

    # 8. The response's audio_content is binary. Write it to a file.
    with open(output_filepath, "wb") as out:
        out.write(response.audio_content)
        print(f'Audio content successfully written to file "{output_filepath}"')
    #print(response)
    # 9. Return the response structure without the audio_content
    # Convert the protobuf response object to a dictionary.
    try:
        # Attempt the standard method first
        response_dict = MessageToDict(response)
        
    except Exception as e:
        if "DESCRIPTOR" in str(e):
            print("Falling back to internal Protobuf dictionary conversion...")
            
            # --- THE WORKAROUND ---
            # The 'response' object is often an instance of google.protobuf.Message
            # We can leverage the built-in .to_dict() method from the underlying 'proto' library.
            
            try:
                # Note: This requires the 'proto' library, which should be installed 
                # with the Google Cloud client libraries.
                import proto 
                response_dict = proto.Message.to_dict(response)
                
            except Exception as fallback_error:
                # If proto.Message.to_dict fails, print the original error 
                # and re-raise to show the core problem
                print(e)
                raise e
        else:
            raise e

    # 4. Return the response structure without the audio_content
    if 'audio_content' in response_dict:
        del response_dict['audio_content']
        print(response_dict)
    return response_dict, full_voice_name

# --- Command Line Example Block ---

if __name__ == "__main__":
    # Ensure the required directory structure exists
    # Note: In a real-world scenario, you'd ensure 'src/audio_piepline/tts' exists.
    # For this example, we'll just use the current directory for the output file
    # and print a warning for the user to ensure the *script location* is correct.
    
    print("\n--- Google Text-to-Speech Client Example ---")
    print("🛑 WARNING: Please ensure this file is saved as `google_client.py` in the `src/audio_piepline/tts` directory.")
    print("🛑 WARNING: Ensure 'google-cloud-texttospeech' is installed (`pip install google-cloud-texttospeech`)")
    print("🛑 WARNING: Ensure you are authenticated (e.g., `gcloud auth application-default login`) and billing is enabled.")
    
    # Define custom voice list for the example
    custom_voice_set = [
        "Charon", "Achird", "Alnilam", "Enceladus", "Aoede",
        "Kore", "Despina", "Pulcherrima"
    ]
    
    # Example 1: Plain English text with the cycling voice selection

    TEXT_EN = """<speak> Candidate name: <phoneme alphabet="ipa" ph="mənod͡ʒ">Manoj</phoneme> <phoneme alphabet="ipa" ph="mənzil">Manzil</phoneme> <mark name="name"/>,
                 is a member of the <phoneme alphabet="ipa" ph="siːpiːaːiː">CPI</phoneme> <phoneme alphabet="ipa" ph="məl">ML</phoneme> <phoneme alphabet="ipa" ph="L">L</phoneme> party <mark name="party"/>,
                   aged 36<mark name="age"/>, 
                   holds a graduate degree (B.A. from H.D. Jain College, Ara in 2015)<mark name="education"/>,
                     has 30 criminal cases on record<mark name="criminal_cases"/>, 
                     assets valued at 3 lakh<mark name="assets"/> 
                     and liabilities amounting to 10 thousand<mark name="liabilities"/></speak>"""
    OUTPUT_FILE_EN = "english_output.mp3"
    
    try:
        response_en, voice_en = synthesize_audio_with_chirp3(
            text_or_ssml=TEXT_EN,
            language_code_2letter="en",
            output_filepath=OUTPUT_FILE_EN,
            voice_options=custom_voice_set # Use the custom voice list
        )
        print(f"\n✅ SUCCESS: English Audio saved to {OUTPUT_FILE_EN} using voice {voice_en}.")
        print("\nAPI Response (excluding audio content):\n", response_en)
        
        # Subsequent call to demonstrate the voice cycling
        print("\n--- Running a second English request to demonstrate voice cycling ---")
        OUTPUT_FILE_EN_2 = "english_output_2.mp3"
        response_en_2, voice_en_2 = synthesize_audio_with_chirp3(
            text_or_ssml=TEXT_EN,
            language_code_2letter="en",
            output_filepath=OUTPUT_FILE_EN_2,
            # DO NOT pass voice_options again, it will continue cycling from the list used above
        )
        print(f"\n✅ SUCCESS: Second English Audio saved to {OUTPUT_FILE_EN_2} using the next voice: {voice_en_2}.")
        
    except Exception as e:
        print(f"\n❌ ERROR during English TTS generation: {e}")

    print("-" * 50)

    # Example 2: Indian Language (Hindi) with SSML input
    TEXT_HI_SSML = """<speak> उम्मीदवार का नाम: <phoneme alphabet="ipa" ph="mənod͡ʒ">मनोज</phoneme> <phoneme alphabet="ipa" ph="mənzil">मंज़िल</phoneme>. <mark name="name"/>, <break time='600ms'/> <phoneme alphabet="ipa" ph="siːpiːaːiː">सीपीआई</phoneme>  <phoneme alphabet="ipa" ph="məl">मल</phoneme> <phoneme alphabet="ipa" ph="L">L</phoneme> पार्टी से संबद्ध हैं<mark name="party"/>,<break time='600ms'/> उम्र ३६ वर्ष<mark name="age"/>, स्नातक शिक्षा प्राप्त है (B.A. from H.D. Jain College, Ara in 2015)<mark name="education"/>, <break time='600ms'/> ३० आपराधिक मामले दर्ज हैं<mark name="criminal_cases"/>,<break time='600ms'/> घोषित संपत्ति ३ लाख की है<mark name="assets"/> <break time='200ms'/>और घोषित ऋण १० हज़ार का है<mark name="liabilities"/></speak>"""
    OUTPUT_FILE_HI = "hindi_output.mp3"
    
    try:
        response_hi, voice_hi = synthesize_audio_with_chirp3(
            text_or_ssml=TEXT_HI_SSML,
            language_code_2letter="hi",
            output_filepath=OUTPUT_FILE_HI,
            # Note: Voice cycling continues from where the previous call left off
        )
        print(f"\n✅ SUCCESS: Hindi Audio saved to {OUTPUT_FILE_HI} using voice {voice_hi}.")
        print("\nAPI Response (excluding audio content):\n", response_hi)
        
    except Exception as e:
        print(f"\n❌ ERROR during Hindi TTS generation: {e}")
    
    print("\n--- Example block finished ---")