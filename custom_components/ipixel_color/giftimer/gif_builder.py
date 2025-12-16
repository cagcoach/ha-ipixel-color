"""GIF generation from timer frames."""

from .formatter import format_time
from .renderer import get_font, measure_text, create_frame, update_frame, create_palette

# Default colors: green on black
DEFAULT_BG = (0, 0, 0)
DEFAULT_FG = (0, 255, 0)


def build_timer_gif(duration_seconds, output_path, font_size=72, bg=DEFAULT_BG, fg=DEFAULT_FG,
                    font_path=None, width=None, height=None, static=False):
    """Build a countdown timer GIF or static image.

    Args:
        duration_seconds: Time to display/countdown from in seconds
        output_path: Path to save the output file
        font_size: Font size in pixels
        bg: Background color as RGB tuple
        fg: Foreground/text color as RGB tuple
        font_path: Path to TTF font file, or None for default
        width: Image width, or None for auto
        height: Image height, or None for auto
        static: If True, generate a single-frame static image instead of animated GIF

    Returns:
        Number of frames (1 for static, duration_seconds+1 for animated)
    """
    font = get_font(font_size, font_path)
    palette = create_palette(bg, fg)
    padding = 20

    # Calculate image size from longest possible text, or use provided size
    max_text = format_time(duration_seconds)
    if duration_seconds <= 599:  # Could show 9:59
        max_text = "9:59"
    text_w, text_h, _ = measure_text(max_text, font)

    if width is None:
        width = text_w + 2 * padding
    if height is None:
        height = text_h + 2 * padding

    if static:
        # Generate single static frame showing the duration
        time_text = format_time(duration_seconds)
        frame, _, _ = create_frame(time_text, width, height, font, palette)

        # Save as single-frame GIF (or PNG based on extension)
        if output_path.lower().endswith('.png'):
            frame.convert("RGB").save(output_path, format="PNG")
        else:
            frame.save(output_path, format="GIF")

        return 1

    # Generate animated countdown GIF
    frames = []
    durations = []
    prev_frame = None
    prev_text = None
    text_x, text_y = 0, 0

    for remaining in range(duration_seconds, -1, -1):
        current_text = format_time(remaining)

        if remaining == 0:
            # Inverted colors for final frame
            inverted_palette = create_palette(fg, bg)
            frame, text_x, text_y = create_frame(current_text, width, height, font, inverted_palette)
            durations.append(65535)  # Max GIF duration (65535ms)
        elif prev_frame is None or len(current_text) != len(prev_text):
            frame, text_x, text_y = create_frame(current_text, width, height, font, palette)
            durations.append(1000)
        else:
            frame = update_frame(prev_frame, prev_text, current_text, text_x, text_y, font)
            durations.append(1000)

        frames.append(frame)
        prev_frame = frame
        prev_text = current_text

    # Save GIF (loop=1 means play once, no repeat)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=1,
        optimize=True
    )

    return len(frames)
