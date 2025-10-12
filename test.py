from pathlib import Path

from moviepy import ColorClip, CompositeVideoClip, TextClip


FONT_PATH = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"
VIDEO_SIZE = (1080, 1920)  # vertical video for shorts
TEXTBOX_DEFAULT_WIDTH = 900
CLIP_DURATION = 5
FPS = 24
OUTPUT_DIR = Path("outputs/hindi_text_variations")

VARIATIONS = [
    {"name": "01_short_phrase", "text": "भारत मेरा देश है।", "fontsize": 150},
    {"name": "02_urgent_call", "text": "अब या कभी नहीं!", "fontsize": 170},
    {"name": "03_warm_smile", "text": "मुस्कुराइए, दुनिया आपकी मुस्कान से रोशन होती है।", "fontsize": 130},
    {"name": "04_strength_of_heart", "text": "दिल से बड़ा कोई नहीं।", "fontsize": 150},
    {
        "name": "05_dreams_takeoff",
        "text": "सपनों की उड़ान मेहनत की रफ़्तार से बढ़ती है।",
        "fontsize": 125,
    },
    {
        "name": "06_new_beginning",
        "text": "हर सुबह नई उम्मीद जगाती है और नई कहानी लिखती है।",
        "fontsize": 120,
    },
    {
        "name": "07_make_possible",
        "text": "दृढ़ निश्चय और लगन से असंभव को संभव बनाया जा सकता है।",
        "fontsize": 115,
        "textbox_width": 820,
    },
    {
        "name": "08_self_belief",
        "text": "खुद पर भरोसा रखो, दुनिया एक दिन तुम्हारा साथ देगी।",
        "fontsize": 120,
    },
    {
        "name": "09_time_value",
        "text": "समय अमूल्य है; इसे सही दिशा में निवेश करें और फर्क देखें।",
        "fontsize": 115,
        "textbox_width": 780,
    },
    {
        "name": "10_where_there_is_will",
        "text": "जहाँ चाह वहाँ राह, बस कदम बढ़ाने की देर है।",
        "fontsize": 125,
    },
    {
        "name": "11_small_steps",
        "text": "छोटे कदम मिलकर बड़ी मंज़िल तक पहुँचाते हैं, बस निरंतर बने रहें।",
        "fontsize": 110,
    },
    {
        "name": "12_willpower_discipline",
        "text": "इच्छा शक्ति और अनुशासन सफलता की सबसे मजबूत सीढ़ियाँ हैं।",
        "fontsize": 110,
        "textbox_width": 760,
    },
    {
        "name": "13_story_of_success",
        "text": "सफलता की कहानी धैर्य, अभ्यास और आत्मविश्वास से लिखी जाती है।",
        "fontsize": 115,
    },
    {
        "name": "14_learn_today",
        "text": "आज कुछ नया सीखो ताकि कल दुनिया तुम्हें नई नज़र से देखे।",
        "fontsize": 120,
    },
    {
        "name": "15_face_challenges",
        "text": "हर चुनौती हमें मजबूत बनाती है, बस हिम्मत रखो और आगे बढ़ो।",
        "fontsize": 115,
        "textbox_width": 820,
    },
]


def build_text_clip(text: str, fontsize: int, textbox_width: int) -> TextClip:
    """Return a centered TextClip for the given text."""
    return (
        TextClip(
            text=text,
            font=FONT_PATH,
            font_size=fontsize,
            color="white",
            method="caption",
            size=(textbox_width, None),
            text_align="center",
            duration=CLIP_DURATION
        )
    )


def render_variations() -> None:
    """Generate one video per variation to evaluate layout constraints."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    background = ColorClip(
        size=VIDEO_SIZE, color=(0, 0, 0), duration=CLIP_DURATION
    )

    for variation in VARIATIONS:
        textbox_width = variation.get("textbox_width", TEXTBOX_DEFAULT_WIDTH)
        text_clip = build_text_clip(
            text=variation["text"],
            fontsize=variation["fontsize"],
            textbox_width=textbox_width,
        )

        final_clip = CompositeVideoClip([background, text_clip])
        output_path = OUTPUT_DIR / f"hindi_text_{variation['name']}.mp4"
        final_clip.write_videofile(
            output_path.as_posix(),
            fps=FPS,
            codec="libx264",
            audio=False,
            preset="medium",
            threads=2,
        )


if __name__ == "__main__":
    render_variations()
