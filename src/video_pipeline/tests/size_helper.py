# text_wrap.py
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Try to use advanced shaping if Pillow supports it
try:
    from PIL import ImageFont as _IF
    _LAYOUT_ENGINE = _IF.LAYOUT_RAQM  # uses harfbuzz/fribidi when available
except Exception:
    _LAYOUT_ENGINE = None

def load_font(font_path: str, font_size: int, index: int | None = None) -> ImageFont.FreeTypeFont:
    """
    Loads TTF/OTF/TTC font. Use `index` for .ttc collections (e.g., pick a weight).
    """
    kwargs = {"font": font_path, "size": font_size}
    if index is not None: kwargs["index"] = index
    # Prefer RAQM layout if supported
    if _LAYOUT_ENGINE is not None:
        kwargs["layout_engine"] = _LAYOUT_ENGINE
    return ImageFont.truetype(**kwargs)

def _measure(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """
    Returns (width_px, height_px) for a single-line string.
    """
    # Tiny canvas just to compute an accurate bbox
    img = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(img)
    # textbbox is accurate for complex scripts if RAQM is active
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    return (r - l, b - t)

def wrap_text_no_breaks(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width_px: int,
    line_spacing_ratio: float = 0.2
) -> dict:
    """
    Word-wraps `text` so that each line's pixel width <= `max_width_px` (when possible),
    without breaking words. Respects explicit newlines in input.

    Returns:
      {
        "lines": [str, ...],
        "line_sizes": [(w,h), ...],
        "block_width": int,
        "block_height": int,
        "line_spacing_px": int
      }
    """
    lines: list[str] = []
    line_sizes: list[tuple[int, int]] = []

    # Split into paragraphs (preserve user's explicit breaks)
    paragraphs = text.splitlines() or [""]

    for para in paragraphs:
        words = para.split()  # split on whitespace; hindi/english both OK when words are space-delimited
        if not words:
            # Keep blank line
            lines.append("")
            line_sizes.append(_measure(" ", font))
            continue

        current = ""
        for w in words:
            candidate = w if not current else f"{current} {w}"
            cw, ch = _measure(candidate, font)
            if cw <= max_width_px:
                current = candidate
            else:
                if current == "":
                    # Single super-long token (rare). Put it on its own line (may overflow).
                    lines.append(w)
                    line_sizes.append(_measure(w, font))
                    current = ""
                else:
                    lines.append(current)
                    line_sizes.append(_measure(current, font))
                    current = w

        if current:
            lines.append(current)
            line_sizes.append(_measure(current, font))

    # Compute block metrics
    base_h = max((h for _, h in line_sizes), default=_measure(" ", font)[1])
    line_spacing_px = int(round(base_h * line_spacing_ratio))
    block_width = max((w for w, _ in line_sizes), default=0)
    block_height = sum(h for _, h in line_sizes) + line_spacing_px * max(0, len(lines) - 1)

    return {
        "lines": lines,
        "line_sizes": line_sizes,
        "block_width": block_width,
        "block_height": block_height,
        "line_spacing_px": line_spacing_px,
    }