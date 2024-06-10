from moviepy.editor import *

from generate_videos.scripts.constants import TEXT_CLIP_PROPS

def generate_video_part(background,video_text,clip_duration, center_image=None, profile_picture=None, party_picture=None):
    
    background = ImageClip(background, duration=clip_duration)
    if center_image:
        text = TextClip(video_text.get("name"," ").capitalize(),size=(int(background.w *0.8),100), align=TEXT_CLIP_PROPS.get('align','West'), font=TEXT_CLIP_PROPS.get('font','Futura-Bold'), fontsize=TEXT_CLIP_PROPS.get('fontsize',70), color=TEXT_CLIP_PROPS.get('color','White'), method=TEXT_CLIP_PROPS.get('method','caption'), stroke_color=TEXT_CLIP_PROPS.get('stroke_color','GhostWhite'), stroke_width=TEXT_CLIP_PROPS.get('stroke_width',1)).set_position(('center','top')).set_duration(clip_duration)
        text2 = TextClip(video_text.get("content"," ").upper(), size=(int(background.w *0.9),None), align=TEXT_CLIP_PROPS.get('align','South'), font=TEXT_CLIP_PROPS.get('font','Futura-Bold'), fontsize=TEXT_CLIP_PROPS.get('fontsize',120), color=TEXT_CLIP_PROPS.get('color','White'), method=TEXT_CLIP_PROPS.get('method','caption'), stroke_color=TEXT_CLIP_PROPS.get('stroke_color','GhostWhite'), stroke_width=TEXT_CLIP_PROPS.get('stroke_width',1)).set_position(('center','bottom')).set_duration(clip_duration)
    else:
        text = TextClip(video_text.get("name"," ").capitalize(),size=(int(background.w *0.8),100), align=TEXT_CLIP_PROPS.get('align','West'), font=TEXT_CLIP_PROPS.get('font','Futura-Bold'), fontsize=TEXT_CLIP_PROPS.get('fontsize',70), color=TEXT_CLIP_PROPS.get('color','White'), method=TEXT_CLIP_PROPS.get('method','caption'), stroke_color=TEXT_CLIP_PROPS.get('stroke_color','GhostWhite'), stroke_width=TEXT_CLIP_PROPS.get('stroke_width',1)).set_position((0.1,0.35),relative=True).set_duration(clip_duration)
        text2 = TextClip(video_text.get("content"," ").upper(), size=(int(background.w *0.9),None), align=TEXT_CLIP_PROPS.get('align','North'), font=TEXT_CLIP_PROPS.get('font','Futura-Bold'), fontsize=TEXT_CLIP_PROPS.get('fontsize',120), color=TEXT_CLIP_PROPS.get('color','White'), method=TEXT_CLIP_PROPS.get('method','caption'), stroke_color=TEXT_CLIP_PROPS.get('stroke_color','GhostWhite'), stroke_width=TEXT_CLIP_PROPS.get('stroke_width',1)).set_position((0.05,0.43),relative=True).set_duration(clip_duration)

    clips=[background, text, text2]
    if center_image and os.path.isfile(center_image):
        profile= ImageClip(center_image).set_duration(clip_duration).set_position('center').resize(height=background.h*0.4, width=background.w*0.4).crossfadein(clip_duration*0.1).crossfadeout(clip_duration*0.2)

        clips.append(profile)

    if profile_picture and os.path.isfile(profile_picture):
        profile_top= ImageClip(profile_picture).set_duration(clip_duration).set_position(('left','top')).resize(height=background.h*0.2, width=background.w*0.2)

        clips.append(profile_top)

    if party_picture and os.path.isfile(party_picture):
        profile_top= ImageClip(party_picture).set_duration(clip_duration).set_position(('right','top')).resize(height=background.h*0.2, width=background.w*0.2)

        clips.append(profile_top)

    return CompositeVideoClip(clips)


