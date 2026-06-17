"""Weather clock bitmap rendering for iPIXEL Color displays."""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageDraw, ImageFont

from ..fonts import get_font_path

_LOGGER = logging.getLogger(__name__)

WEEKDAYS_TR = ["PZT", "SAL", "CAR", "PER", "CUM", "CMT", "PAZ"]
MONTHS_TR = [
    "OCAK",
    "SUBAT",
    "MART",
    "NISAN",
    "MAYIS",
    "HAZ",
    "TEM",
    "AGU",
    "EYL",
    "EKIM",
    "KAS",
    "ARA",
]


def render_weather_clock_to_png(
    *,
    width: int,
    height: int,
    condition: str,
    temperature: float | int | None,
    hour_minute: str,
    weekday_index: int,
    day: int,
    month: int,
    custom_text: str | None = None,
    font_name: str = "7x5.ttf",
    font_size: float = 7.5,
    background_color: str = "000000",
) -> bytes:
    """Render a 96x16 weather clock layout to PNG bytes."""
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid display dimensions: {width}x{height}")

    image = Image.new("RGB", (width, height), _hex_to_rgb(background_color))
    draw = ImageDraw.Draw(image)
    font = _load_font(font_name, font_size)

    icon_width = min(18, width // 4)
    icon_gap = 2
    _draw_weather_icon(draw, condition, icon_width)

    text_x = icon_width + icon_gap
    text_width = width - text_x
    if custom_text:
        weekday_text, date_text = _split_top_text(custom_text)
    else:
        weekday_text = WEEKDAYS_TR[weekday_index]
        date_text = f"{day} {MONTHS_TR[month - 1]}"
    temp_text = _format_temperature_value(temperature)

    _draw_date_row(
        draw,
        weekday_text,
        date_text,
        text_x,
        text_width,
        font,
    )
    _draw_bottom_row(
        draw,
        hour_minute,
        temp_text,
        text_x,
        text_width,
        font,
    )

    image = image.rotate(180)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_data = buffer.getvalue()
    _LOGGER.debug(
        "Rendered weather clock PNG: condition=%s size=%dx%d payload=%d",
        condition,
        width,
        height,
        len(png_data),
    )
    return png_data


def _load_font(font_name: str, font_size: float) -> ImageFont.ImageFont:
    """Load configured pixel font."""
    font_path = get_font_path(font_name)
    if font_path:
        _LOGGER.debug("Using weather clock font file: %s size=%.1f", font_path, font_size)
        return ImageFont.truetype(str(font_path), font_size)

    _LOGGER.warning("Weather clock font %s not found; using PIL default", font_name)
    return ImageFont.load_default()


def _draw_weather_icon(draw: ImageDraw.ImageDraw, condition: str, size: int) -> None:
    """Draw a compact colorful weather icon in the left 16x16 cell."""
    condition = (condition or "").lower()

    if condition in {"sunny", "clear"}:
        _draw_sun(draw, 8, 8)
    elif condition == "clear-night":
        _draw_moon(draw)
    elif condition in {"partlycloudy", "partly-cloudy"}:
        _draw_sun(draw, 6, 6, radius=3)
        _draw_cloud(draw, x=4, y=8)
    elif condition in {"cloudy", "fog"}:
        _draw_cloud(draw, x=2, y=4)
        if condition == "fog":
            for y in (12, 14):
                draw.line((2, y, size - 2, y), fill=(145, 170, 185))
    elif condition in {"rainy", "pouring"}:
        _draw_cloud(draw, x=2, y=2)
        for x, y in ((4, 11), (8, 12), (12, 11)):
            draw.line((x, y, x - 1, y + 2), fill=(50, 170, 255))
    elif condition == "lightning":
        _draw_cloud(draw, x=2, y=2)
        draw.polygon([(8, 9), (6, 14), (10, 11), (8, 15)], fill=(255, 220, 40))
    elif condition in {"snowy", "snowy-rainy"}:
        _draw_cloud(draw, x=2, y=2)
        for x, y in ((4, 13), (8, 12), (12, 13)):
            draw.point((x, y), fill=(210, 240, 255))
            draw.point((x - 1, y), fill=(210, 240, 255))
            draw.point((x + 1, y), fill=(210, 240, 255))
    else:
        draw.ellipse((3, 3, 12, 12), outline=(80, 190, 255), width=2)
        draw.point((8, 8), fill=(255, 255, 255))


def _draw_sun(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    radius: int = 4,
) -> None:
    """Draw a tiny sun."""
    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=(255, 190, 30),
    )
    for x1, y1, x2, y2 in (
        (cx, 0, cx, 2),
        (cx, 14, cx, 15),
        (0, cy, 2, cy),
        (14, cy, 15, cy),
        (2, 2, 3, 3),
        (13, 2, 12, 3),
        (2, 13, 3, 12),
        (13, 13, 12, 12),
    ):
        draw.line((x1, y1, x2, y2), fill=(255, 225, 80))


def _draw_moon(draw: ImageDraw.ImageDraw) -> None:
    """Draw a tiny crescent moon."""
    draw.ellipse((3, 2, 12, 12), fill=(245, 230, 150))
    draw.ellipse((7, 1, 14, 10), fill=(0, 0, 0))
    draw.point((13, 3), fill=(180, 220, 255))
    draw.point((12, 12), fill=(180, 220, 255))


def _draw_cloud(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Draw a tiny cloud."""
    color = (185, 210, 225)
    shade = (120, 150, 170)
    draw.ellipse((x + 1, y + 1, x + 7, y + 7), fill=color)
    draw.ellipse((x + 5, y - 1, x + 12, y + 7), fill=color)
    draw.rectangle((x + 3, y + 4, x + 14, y + 9), fill=color)
    draw.line((x + 3, y + 9, x + 14, y + 9), fill=shade)


def _draw_fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """Draw text if it fits, trimming from the end if needed."""
    candidate = text
    while candidate and _text_width(draw, candidate, font) > max_width:
        candidate = candidate[:-1]
    draw.text(xy, candidate, font=font, fill=fill)


def _draw_date_row(
    draw: ImageDraw.ImageDraw,
    weekday_text: str,
    date_text: str,
    x: int,
    max_width: int,
    font: ImageFont.ImageFont,
) -> None:
    """Draw weekday in blue and date in white."""
    y = -1
    weekday_color = (80, 190, 255)
    date_color = (245, 245, 245)
    space_width = _text_width(draw, " ", font)
    weekday_width = _text_width(draw, weekday_text, font)
    date_x = x + weekday_width + space_width
    available_date_width = max_width - weekday_width - space_width

    draw.text((x, y), weekday_text, font=font, fill=weekday_color)
    _draw_fit_text(
        draw,
        date_text,
        (date_x, y),
        available_date_width,
        font,
        fill=date_color,
    )


def _split_top_text(text: str) -> tuple[str, str]:
    """Split custom top-row text into blue and white segments."""
    parts = text.strip().split(maxsplit=1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _draw_bottom_row(
    draw: ImageDraw.ImageDraw,
    hour_minute: str,
    temp_text: str,
    x: int,
    max_width: int,
    font: ImageFont.ImageFont,
) -> None:
    """Draw temperature and time on the bottom row."""
    y = 8
    temp_color = (255, 120, 60)
    draw.text((x, y), temp_text, font=font, fill=temp_color)
    if temp_text != "--":
        degree_x = x + _text_width(draw, temp_text, font) + 1
        _draw_degree_dots(draw, degree_x, y + 1, fill=temp_color)

    time_width = _text_width(draw, hour_minute, font)
    draw.text(
        (x + max_width - time_width, y),
        hour_minute,
        font=font,
        fill=(255, 224, 120),
    )


def _draw_degree_dots(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    fill: tuple[int, int, int],
) -> None:
    """Draw a degree mark as four explicit pixels."""
    for point in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
        draw.point(point, fill=fill)


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> int:
    """Return text width."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _format_temperature_value(temperature: float | int | None) -> str:
    """Format temperature number; degree mark is drawn manually."""
    if temperature is None:
        return "--"
    return f"{round(float(temperature))}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a six-digit hex color to RGB."""
    normalized = hex_color.lstrip("#")
    if len(normalized) != 6:
        raise ValueError(f"Invalid hex color length: {hex_color}")
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )
