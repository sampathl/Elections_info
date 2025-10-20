import moviepy as mp
from size_helper import load_font, wrap_text_no_breaks

VIDEO_W, VIDEO_H = 1080, 1920
LEFT_PAD, RIGHT_PAD = 96, 96
MAX_TEXT_WIDTH = VIDEO_W - LEFT_PAD - RIGHT_PAD
FONT_SIZE = 90

# Pick your fonts (Devanagari + Latin)
# macOS examples:
# Hindi: system Kohinoor Devanagari TTC (use index to pick variant if needed)
DEVANAGARI_FONT_PATH = "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc"
# English: choose a Latin font you like (or use a Noto Sans .ttf you installed)
LATIN_FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"  # replace with your preferred file

# Load fonts
hi_font = load_font(DEVANAGARI_FONT_PATH, FONT_SIZE, index=0)   # index may pick Regular
en_font = load_font(LATIN_FONT_PATH, FONT_SIZE)

text_hi = "भारत मेरा देश है,"
text_en = "We take pride in unity in diversity. diversitydiversitydiversity.."

# Choose font based on language (simple example)
text = text_hi  # or text_en
font = hi_font  # or en_font

layout = wrap_text_no_breaks(text, font, max_width_px=MAX_TEXT_WIDTH, line_spacing_ratio=0.18)

# Build a single multiline string with explicit line breaks for MoviePy
multiline_text = "\n".join(layout["lines"])

text_w = layout["block_width"]
text_h = layout["block_height"]
top_pad = 20

txt = mp.TextClip(
    text=multiline_text,
    font=DEVANAGARI_FONT_PATH,
    font_size=FONT_SIZE,
    color="white",
    vertical_align="top",
    method="caption",
    size=(max(text_w, 1), max(text_h, 1)),
)



# Optional: create a background to visualize placement
#bg = mp.ColorClip(size=(VIDEO_W, VIDEO_H), color=(16,16,16), duration=5)
bg = mp.VideoFileClip(str("tests/video_pipeline/blue/board.mp4")).subclipped(0, 5)

# Position: center horizontally, some bottom offset
x = (VIDEO_W - layout["block_width"]) // 2
y = VIDEO_H - layout["block_height"] - 200  # 200px margin from bottom

txt = txt.with_position((0, top_pad)).with_duration(5)

print(x,y,top_pad,VIDEO_H,VIDEO_W,layout["block_height"],layout["block_width"])

final = mp.CompositeVideoClip([bg, txt])
final.write_videofile("wrapped_text.mp4", fps=30)