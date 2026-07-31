"""Compose an MDI icon, an image, and/or up to 4 text elements on one canvas.

Unlike send_mdi_icon (which centers one icon on the whole panel) or the
native send_text (device-rendered, no positioning control, whole-panel
only), this lets you place icons, an image, and several text labels
independently, each at its own top-left (x, y) position - then sends the
whole composed canvas as a single image (static PNG, or an animated GIF
if anything scrolls or blinks).

Native device-side text scrolling (pypixelcolor's send_text) is lighter
and faster, but it replaces the whole panel with one animated string -
it has no concept of a sub-region, and can't be combined with an icon or
other text. Scrolling/blinking within a composed layout is only
achievable by generating the frames ourselves, which is inherently
heavier to transfer - the single biggest lever to reduce transfer time
is scroll_step (fewer, bigger jumps = far fewer frames).
"""
from __future__ import annotations

import io
import logging
import math

import aiohttp
from PIL import Image, ImageDraw, ImageFont

from ..color import hex_to_rgb
from ..fonts import get_font_locations, get_font_path
from .mdi_icon import fetch_mdi_svg, render_mdi_icon

_LOGGER = logging.getLogger(__name__)

# Smallest bundled bitmap font - use this when no explicit font is requested
DEFAULT_SMALL_FONT = "3x5-de"
DEFAULT_SMALL_FONT_SIZE = 6

# Up to 4 independent text elements per layout (same idea as "lines" on the panel)
MAX_TEXT_ELEMENTS = 4

# Up to 4 independent MDI icons per layout
MAX_ICON_ELEMENTS = 4

# Hard cap on generated frames, in case multiple independently-looping
# scroll/blink cycles have a combined length (LCM) that would otherwise be huge
MAX_ANIMATION_FRAMES = 240


def _lcm(a: int, b: int) -> int:
    """Least common multiple of two positive integers."""
    return a * b // math.gcd(a, b)


def _split_word_to_width(word: str, font_obj: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    """Split a single space-free word into pieces that each fit max_width.

    Used as a fallback when a whole 'word' (e.g. a long digit string with
    no spaces) is wider than max_width on its own - breaks it character by
    character instead of letting it overflow.
    """
    pieces: list[str] = []
    current = ""
    for ch in word:
        candidate = current + ch
        width = draw.textbbox((0, 0), candidate, font=font_obj)[2]
        if width <= max_width or not current:
            current = candidate
        else:
            pieces.append(current)
            current = ch
    if current:
        pieces.append(current)
    return pieces


def _wrap_line(line: str, font_obj: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    """Greedily word-wrap a single line to fit within max_width pixels.

    Args:
        line: A single line of text (no '\\n').
        font_obj: The font to measure with.
        draw: An ImageDraw instance used for measurement only.
        max_width: Maximum line width in pixels.

    Returns:
        List of wrapped sub-lines. A word wider than max_width even on its
        own (e.g. a long digit string with no spaces) is split character
        by character instead of overflowing. Note: word wrapping reflows
        text and does not preserve exact original spacing between words -
        if you need exact spacing (e.g. manual alignment via leading/
        trailing spaces), disable wrap.
    """
    words = line.split(" ")
    wrapped: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font_obj)[2]
        if width <= max_width:
            current = candidate
            continue

        if current:
            wrapped.append(current)
            current = ""

        word_width = draw.textbbox((0, 0), word, font=font_obj)[2]
        if word_width <= max_width:
            current = word
        else:
            pieces = _split_word_to_width(word, font_obj, draw, max_width)
            if pieces:
                wrapped.extend(pieces[:-1])
                current = pieces[-1]
    if current:
        wrapped.append(current)
    return wrapped


def render_text_element(
    text: str,
    font_size: float = DEFAULT_SMALL_FONT_SIZE,
    font_name: str | None = None,
    color_hex: str = "ffffff",
    max_width: int | None = None,
    line_spacing: int = 1,
    align: str = "left",
) -> Image.Image:
    """Render text sized to its own advance width/height (no fixed canvas).

    Explicit '\\n' in the text always forces a line break, regardless of
    max_width. If max_width is given, each resulting line is additionally
    word-wrapped to fit within it (e.g. to avoid running off the edge of
    the panel) - but wrapping reflows words and does not preserve exact
    spacing; leave max_width=None (wrap=False at the caller level) if you
    need leading/trailing/internal spaces preserved exactly as given (e.g.
    for manual alignment).

    Width is measured via the font's advance metrics, not the ink bounding
    box, so leading/trailing spaces contribute to the width instead of
    being invisibly cropped away.

    Args:
        text: Text to render. '\\n' forces a line break.
        font_size: Font size in pixels (can be fractional).
        font_name: Bundled font name (e.g. '3x5-de', '5x5', '7x5',
            'Lepidos', 'OpenSans-Light', 'WP7xn'), or None for the
            smallest bundled font.
        color_hex: Text color in hex, with or without '#'.
        max_width: If given, word-wrap each line to fit within this many
            pixels. None disables automatic wrapping (only '\\n' breaks lines).
        line_spacing: Extra vertical gap between lines, in pixels.
        align: Horizontal alignment of each line within the block's own
            width: 'left' (default), 'right', or 'center'. Only matters
            with multiple lines of different widths, or when the caller
            positions this block by an edge other than its left.

    Returns:
        RGBA PIL Image sized to the rendered (possibly multi-line) text.
    """
    locations = get_font_locations()
    font_path = get_font_path(font_name or DEFAULT_SMALL_FONT, locations)

    # Accept both a real newline character and a literal '\n' (two chars,
    # backslash + n) as a forced line break - the latter is what arrives
    # when someone types \n into a plain GUI text field (no YAML escape
    # processing happens there), rather than an actual newline.
    text = text.replace("\\n", "\n")

    if font_path is not None:
        font_obj = ImageFont.truetype(str(font_path), size=max(1, round(font_size)))
    else:
        _LOGGER.warning("Font '%s' not found, falling back to PIL default", font_name)
        font_obj = ImageFont.load_default()

    probe = Image.new("RGBA", (1, 1))
    probe_draw = ImageDraw.Draw(probe)

    # Explicit '\n' always breaks; max_width additionally wraps each of those lines
    raw_lines = text.split("\n")
    if max_width is not None:
        lines: list[str] = []
        for raw_line in raw_lines:
            lines.extend(_wrap_line(raw_line, font_obj, probe_draw, max_width) or [""])
    else:
        lines = raw_lines

    # Width via advance metrics (preserves leading/trailing spaces); height
    # via a uniform per-line box so blank/whitespace-only lines still take
    # up vertical space instead of collapsing to nothing.
    line_widths = [max(1, round(probe_draw.textlength(line, font=font_obj))) for line in lines]
    line_boxes = [probe_draw.textbbox((0, 0), line or " ", font=font_obj) for line in lines]
    line_heights = [max(1, box[3] - box[1]) for box in line_boxes]

    text_w = max(line_widths)
    text_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Render onto a grayscale mask first, then threshold to pure black/white
    # (no gray edge pixels). FreeType antialiases outlines by default, which
    # blurs the crisp square edges a pixel-style font is supposed to have on
    # an LED matrix - thresholding removes that blur regardless of font size.
    mask_img = Image.new("L", (text_w, text_h), 0)
    mask_draw = ImageDraw.Draw(mask_img)

    y_offset = 0
    for line, box, height, width in zip(lines, line_boxes, line_heights, line_widths):
        if align == "right":
            x_offset = text_w - width
        elif align == "center":
            x_offset = (text_w - width) // 2
        else:
            x_offset = 0
        mask_draw.text((x_offset - box[0], y_offset - box[1]), line, font=font_obj, fill=255)
        y_offset += height + line_spacing

    mask_img = mask_img.point(lambda p: 255 if p >= 128 else 0)

    rgb = hex_to_rgb(color_hex)
    img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
    solid = Image.new("RGBA", (text_w, text_h), rgb + (255,))
    img.paste(solid, (0, 0), mask=mask_img)

    return img


async def _build_base_canvas(
    canvas_width: int,
    canvas_height: int,
    session: aiohttp.ClientSession,
    bg_color_hex: str,
    icons: list[dict] | None = None,
    image_bytes: bytes | None = None,
    image_x: int = 0,
    image_y: int = 0,
    image_width: int | None = None,
    image_height: int | None = None,
) -> tuple[Image.Image, list[dict]]:
    """Build the background+non-blinking-icons+image canvas.

    Returns (canvas, blinking_icons) - blinking icons are rendered here
    (so they're only fetched/rasterized once) but not pasted onto the
    canvas, since they need to be drawn per-frame in the animation loop.

    Args:
        icons: List of up to MAX_ICON_ELEMENTS dicts, each with: icon
            (required, MDI name), x, y, size, color_hex, blink,
            blink_interval_ms (all optional besides icon). Extra items
            beyond the limit are ignored (with a warning).
    """
    bg_rgb = hex_to_rgb(bg_color_hex)
    canvas = Image.new("RGB", (canvas_width, canvas_height), bg_rgb)

    icons = [i for i in (icons or []) if i.get("icon")]
    if len(icons) > MAX_ICON_ELEMENTS:
        _LOGGER.warning(
            "%d icons given, only the first %d are used", len(icons), MAX_ICON_ELEMENTS,
        )
        icons = icons[:MAX_ICON_ELEMENTS]

    blinking_icons = []
    for item in icons:
        x = int(item.get("x", 0))
        y = int(item.get("y", 0))
        size_px = item.get("size") or min(canvas_width, canvas_height)
        color_hex = item.get("color_hex", "ffffff")
        svg_markup = await fetch_mdi_svg(item["icon"], session)
        icon_img = render_mdi_icon(svg_markup, size_px, color_hex)

        if item.get("blink"):
            blinking_icons.append({
                "x": x, "y": y, "img": icon_img,
                "blink_interval_ms": int(item.get("blink_interval_ms", 500)),
            })
        else:
            canvas.paste(icon_img, (x, y), mask=icon_img)

    if image_bytes is not None:
        img = Image.open(io.BytesIO(image_bytes))
        if getattr(img, "is_animated", False):
            img.seek(0)  # static insertion: first frame only
        img = img.convert("RGBA")
        if image_width or image_height:
            target_w = image_width or img.width
            target_h = image_height or img.height
            img = img.resize((target_w, target_h))
        canvas.paste(img, (image_x, image_y), mask=img)

    return canvas, blinking_icons


def _prepare_text_item(
    canvas_width: int,
    item: dict,
    scroll_step: int,
    scroll_gap: int,
) -> dict:
    """Render one text item and decide whether it needs to scroll.

    `x` is the anchor point according to `align`: for 'left' (default) it's
    the text block's left edge, for 'right' its right edge, for 'center'
    its horizontal center - in all cases `x` is where that reference point
    of the (possibly multi-line) text block ends up on the canvas.
    Scrolling text always anchors its left edge at `x` and moves rightward
    through the available space, regardless of `align` (a moving block has
    no fixed edge to anchor by the time it's mid-scroll).

    Args:
        canvas_width: Device width, used to compute available space for
            wrapping/scrolling.
        item: Dict with keys 'text' (required), 'x', 'y', 'size', 'font',
            'color_hex', 'wrap', 'scroll', 'line_spacing', 'align',
            'blink', 'blink_interval_ms' (all optional).
        scroll_step: Pixels moved per animation frame (shared by all
            scrolling items, so their loops can be kept in sync).
        scroll_gap: Blank pixels between loop passes (shared).

    Returns:
        A prepared dict ready for static pasting or frame-by-frame scrolling.
    """
    x = int(item.get("x", 0))
    y = int(item.get("y", 0))
    size = item.get("size", DEFAULT_SMALL_FONT_SIZE)
    font = item.get("font")
    color_hex = item.get("color_hex", "ffffff")
    wrap = item.get("wrap", True)
    scroll = item.get("scroll", False)
    line_spacing = int(item.get("line_spacing", 1))
    align = item.get("align", "left")
    blink = bool(item.get("blink", False))
    blink_interval_ms = int(item.get("blink_interval_ms", 500))

    # Scrolling always measures available space to the right of x (its
    # fixed left-anchor while moving); wrapping/static content measures
    # available space per the chosen anchor instead.
    scroll_avail = max(1, canvas_width - x)
    if align == "right":
        wrap_avail = max(1, x)
    elif align == "center":
        wrap_avail = max(1, 2 * min(x, canvas_width - x))
    else:
        wrap_avail = scroll_avail

    natural_img = render_text_element(
        item["text"], size, font, color_hex, max_width=None,
        line_spacing=line_spacing, align=align,
    )

    if scroll and natural_img.width > scroll_avail:
        strip_w = natural_img.width + scroll_gap
        strip = Image.new("RGBA", (strip_w * 2, natural_img.height), (0, 0, 0, 0))
        strip.paste(natural_img, (0, 0), mask=natural_img)
        strip.paste(natural_img, (strip_w, 0), mask=natural_img)
        n_steps = max(1, strip_w // max(1, scroll_step))
        return {
            "mode": "scroll", "x": x, "y": y, "avail": scroll_avail,
            "strip": strip, "strip_w": strip_w, "n_steps": n_steps,
            "h": natural_img.height, "blink": blink,
            "blink_interval_ms": blink_interval_ms,
        }

    static_img = render_text_element(
        item["text"], size, font, color_hex,
        max_width=(wrap_avail if wrap else None), line_spacing=line_spacing, align=align,
    )

    if align == "right":
        paste_x = x - static_img.width
    elif align == "center":
        paste_x = x - static_img.width // 2
    else:
        paste_x = x

    return {
        "mode": "static", "x": paste_x, "y": y, "img": static_img,
        "blink": blink, "blink_interval_ms": blink_interval_ms,
    }


def _blink_cycle_frames(blink_interval_ms: int, frame_ms: int) -> int:
    """Frames for one full on+off blink cycle, at the shared frame cadence."""
    frames_per_state = max(1, round(blink_interval_ms / max(1, frame_ms)))
    return 2 * frames_per_state


def _is_blink_visible(k: int, blink_interval_ms: int, frame_ms: int) -> bool:
    """Whether a blinking item is in its 'on' state at frame k."""
    frames_per_state = max(1, round(blink_interval_ms / max(1, frame_ms)))
    return (k // frames_per_state) % 2 == 0


async def build_layout_media(
    canvas_width: int,
    canvas_height: int,
    session: aiohttp.ClientSession,
    bg_color_hex: str = "000000",
    icons: list[dict] | None = None,
    image_bytes: bytes | None = None,
    image_x: int = 0,
    image_y: int = 0,
    image_width: int | None = None,
    image_height: int | None = None,
    texts: list[dict] | None = None,
    scroll_step: int = 2,
    scroll_frame_ms: int = 80,
    scroll_gap: int = 16,
) -> tuple[bytes, str]:
    """Compose up to 4 MDI icons, a static image/GIF-first-frame, and up to 4 texts.

    Returns a static PNG unless at least one element scrolls (text only)
    or blinks (text or icons) - in which case a looping animated GIF is
    built, with every scrolling/blinking element's cycle kept in sync via
    the least common multiple of their individual cycle lengths (in
    frames, at the shared scroll_frame_ms cadence), capped at
    MAX_ANIMATION_FRAMES to avoid runaway frame counts on awkward
    combinations.

    Args:
        canvas_width: Device width in pixels.
        canvas_height: Device height in pixels.
        session: aiohttp session for fetching MDI icons (if any).
        bg_color_hex: Canvas background color, hex without '#'.
        icons: List of up to MAX_ICON_ELEMENTS dicts, each with: icon
            (required, MDI name with or without 'mdi:'), x, y, size,
            color_hex, blink, blink_interval_ms (all optional besides
            icon; size defaults to the canvas's smaller dimension,
            color_hex to 'ffffff'). Extra items beyond the limit are
            ignored (with a warning). Icons never scroll.
        image_bytes: Raw bytes of an image/GIF file to insert (only its
            first frame, if animated) at (image_x, image_y). None to skip.
        image_x: Image top-left X position in pixels.
        image_y: Image top-left Y position in pixels.
        image_width: If given, resize the image to this width.
        image_height: If given, resize the image to this height.
        texts: List of up to MAX_TEXT_ELEMENTS dicts, each with:
            text (required), x, y, size, font, color_hex, wrap, scroll,
            line_spacing, align ('left'/'right'/'center'), blink,
            blink_interval_ms (all optional). Extra items beyond the
            limit are ignored (with a warning).
        scroll_step: Pixels moved per animation frame, shared by every
            scrolling text (keeps them moving at the same rate so their
            loops can be synchronized). This is the single biggest lever
            for reducing transfer time - a bigger step means far fewer
            frames for the same text.
        scroll_frame_ms: Duration of each animation frame, in ms. Also
            the timing unit blink_interval_ms is measured against.
        scroll_gap: Blank pixels between loop passes, shared by every
            scrolling text.

    Returns:
        Tuple of (encoded bytes, ".png" or ".gif").
    """
    base_canvas, blinking_icons = await _build_base_canvas(
        canvas_width, canvas_height, session, bg_color_hex,
        icons, image_bytes, image_x, image_y, image_width, image_height,
    )

    texts = [t for t in (texts or []) if t.get("text")]
    if len(texts) > MAX_TEXT_ELEMENTS:
        _LOGGER.warning(
            "%d text elements given, only the first %d are used", len(texts), MAX_TEXT_ELEMENTS,
        )
        texts = texts[:MAX_TEXT_ELEMENTS]

    prepared = [
        _prepare_text_item(canvas_width, item, scroll_step, scroll_gap)
        for item in texts
    ]

    scrolling = [p for p in prepared if p["mode"] == "scroll"]
    any_blink_text = any(p["blink"] for p in prepared)
    needs_animation = bool(scrolling) or any_blink_text or bool(blinking_icons)

    if not needs_animation:
        canvas = base_canvas.copy()
        for item in prepared:
            canvas.paste(item["img"], (item["x"], item["y"]), mask=item["img"])
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue(), ".png"

    total_frames = 1
    for item in scrolling:
        total_frames = _lcm(total_frames, item["n_steps"])
    for item in prepared:
        if item["blink"]:
            total_frames = _lcm(total_frames, _blink_cycle_frames(item["blink_interval_ms"], scroll_frame_ms))
    for item in blinking_icons:
        total_frames = _lcm(total_frames, _blink_cycle_frames(item["blink_interval_ms"], scroll_frame_ms))

    if total_frames > MAX_ANIMATION_FRAMES:
        _LOGGER.warning(
            "Combined animation loop would need %d frames to realign perfectly; "
            "capping at %d (loops may not perfectly resync at the GIF's own loop point)",
            total_frames, MAX_ANIMATION_FRAMES,
        )
        total_frames = MAX_ANIMATION_FRAMES

    frames = []
    for k in range(total_frames):
        frame = base_canvas.copy()

        for item in blinking_icons:
            if _is_blink_visible(k, item["blink_interval_ms"], scroll_frame_ms):
                frame.paste(item["img"], (item["x"], item["y"]), mask=item["img"])

        for item in prepared:
            if item["blink"] and not _is_blink_visible(k, item["blink_interval_ms"], scroll_frame_ms):
                continue
            if item["mode"] == "static":
                frame.paste(item["img"], (item["x"], item["y"]), mask=item["img"])
            else:
                offset = (k * scroll_step) % item["strip_w"]
                window = item["strip"].crop((offset, 0, offset + item["avail"], item["h"]))
                frame.paste(window, (item["x"], item["y"]), mask=window)
        frames.append(frame)

    # Merge consecutive identical frames (common during the blank gap between
    # loop passes) into one longer-duration frame instead of repeating
    # identical image data - shrinks the transferred payload with no visual
    # difference. Note: for a single long scrolling text with a wide
    # available width, this typically finds nothing to merge - scroll_step
    # remains the main lever for reducing size in that case.
    merged_frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in frames:
        if merged_frames and list(frame.getdata()) == list(merged_frames[-1].getdata()):
            durations[-1] += scroll_frame_ms
        else:
            merged_frames.append(frame)
            durations.append(scroll_frame_ms)

    quantized = [
        f.convert("RGB").quantize(colors=32, method=Image.Quantize.MEDIANCUT)
        for f in merged_frames
    ]

    buf = io.BytesIO()
    quantized[0].save(
        buf, format="GIF", save_all=True, append_images=quantized[1:],
        duration=durations, loop=0, disposal=2, optimize=True,
    )
    return buf.getvalue(), ".gif"
