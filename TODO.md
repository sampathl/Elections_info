Audio Generation

- text to speech calls script,
  - save audio location
  - save output of the tts for timing in the csv
  - save the audio metadata with id

  - add <prosody 	rate="slow" volume="loud"> </prosody> for criminal cases 
  - add <prosody rate="medium" pitch="+1st" volume="default"> for entire speak
  - add <break time="800ms"/> after every mark 
  - try using a combination of all the explored breaks, vocie modulation, and filler words for the adudi to make the better. 
  
- test calls
  - set up test calls for constituencies and exiting winner names

Video Generation

- backgrounds
  - Try sora to make them even better
  - Inital disclaimer screen - with the loading gif, breathing gif, eye movement gif, wistle gif
  - end credits screen
- text overlay
  - understand movie py text overlay patterns and limitations by testing
  - finalize the size for length range and use that calculation for computing
  - verify the font colors for each of the background colors
  - verify the fonts for languages
  - understand and finalize the fonts needed for hindi depiction
- Striching

  - script based on the audio timings
  - how to overlay video, text, audio, audio background
  - finalize the part of the video
  - final script to pull audio, background, text and then generate the video

- video upload script

  - finalize the folder structure for video
  - utilize csv and folder structure for pulling the vido and uploading
  - utilize the same csv to update video id
  - use existing playlist id's for the video inserts.

- Data scraping script
  - individual links for constituencies
  - individual data pulls for the contestes tests.
  - finalize the data scraping outputs
  - finalize csv utilziation
