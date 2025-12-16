"""Frame rendering utilities."""

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FONT_PATHS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def get_font(size, font_path=None):
    """Get a font. Uses font_path if provided, otherwise tries defaults."""
    if font_path:
        return ImageFont.truetype(font_path, size)

    for path in DEFAULT_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def measure_text(text, font):
    """Measure text dimensions."""
    img = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]


def create_palette(bg_color, fg_color):
    """Create a 2-color palette."""
    palette = list(bg_color) + list(fg_color) + [0] * (256 * 3 - 6)
    return palette


def create_frame(text, width, height, font, palette):
    """Create a new frame with centered text (2-color palette)."""
    frame = Image.new("P", (width, height), 0)
    frame.putpalette(palette)
    draw = ImageDraw.Draw(frame)

    text_w, text_h, y_offset = measure_text(text, font)
    x = (width - text_w) // 2
    y = (height - text_h) // 2 - y_offset

    draw.text((x, y), text, font=font, fill=1)
    return frame, x, y


def update_frame(prev_frame, prev_text, new_text, x, y, font):
    """Update only changed characters in a frame (2-color palette)."""
    frame = prev_frame.copy()
    draw = ImageDraw.Draw(frame)

    x_offset = x
    for old_char, new_char in zip(prev_text, new_text):
        bbox = draw.textbbox((x_offset, y), old_char, font=font)
        char_width = bbox[2] - bbox[0]

        if old_char != new_char:
            # Clear and redraw only this character
            draw.rectangle([bbox[0], bbox[1], bbox[2], bbox[3]], fill=0)
            draw.text((x_offset, y), new_char, font=font, fill=1)

        x_offset += char_width

    return frame
