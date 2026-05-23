"""Emoji rendering for iPIXEL Color displays.

Downloads Twemoji PNGs asynchronously (cached locally) and composes them
onto a canvas matching the device dimensions reported by the firmware.
"""
from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

import aiohttp
from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..color import hex_to_rgb

_LOGGER = logging.getLogger(__name__)

TWEMOJI_CDN = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72/{cp}.png"
CACHE_DIRNAME = "ipixel_emoji_cache"
DOWNLOAD_TIMEOUT = 10  # seconds


def _emoji_to_codepoint(emoji: str) -> str:
    """Convert an emoji string to Twemoji's filename codepoint format.

    Twemoji strips the FE0F variation selector but keeps ZWJ sequences
    (e.g. family emojis). Returns codepoints joined by '-'.
    """
    parts = [f"{ord(c):x}" for c in emoji if c != "\ufe0f"]
    return "-".join(parts)


async def _fetch_emoji_png(hass: HomeAssistant, codepoint: str) -> bytes | None:
    """Fetch the Twemoji PNG for a codepoint, with on-disk caching."""
    cache_dir = Path(hass.config.path(".storage", CACHE_DIRNAME))
    await hass.async_add_executor_job(
        lambda: cache_dir.mkdir(parents=True, exist_ok=True)
    )

    cached_path = cache_dir / f"{codepoint}.png"
    if cached_path.exists():
        return await hass.async_add_executor_job(cached_path.read_bytes)

    url = TWEMOJI_CDN.format(cp=codepoint)
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(DOWNLOAD_TIMEOUT):
            async with session.get(url) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Twemoji %s not found at %s (HTTP %s)", codepoint, url, resp.status)
                    return None
                data = await resp.read()
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        _LOGGER.error("Failed to fetch Twemoji %s: %s", codepoint, err)
        return None

    await hass.async_add_executor_job(cached_path.write_bytes, data)
    return data


def _compose_emoji_image(
    emoji_png: bytes,
    canvas_width: int,
    canvas_height: int,
    bg_color: str = "000000",
) -> bytes:
    """Compose an emoji PNG onto a canvas, preserving aspect ratio.

    The emoji is scaled so that its longest side fits within the canvas
    (minus 2px padding) and centered. Background uses bg_color.
    """
    try:
        bg_r, bg_g, bg_b = hex_to_rgb(bg_color)
    except (ValueError, IndexError):
        bg_r, bg_g, bg_b = 0, 0, 0

    canvas = Image.new("RGB", (canvas_width, canvas_height), (bg_r, bg_g, bg_b))

    src = Image.open(io.BytesIO(emoji_png)).convert("RGBA")
    target = min(canvas_width, canvas_height)
    scale = max(1, target - 2) / max(src.width, src.height)
    new_w = max(1, int(src.width * scale))
    new_h = max(1, int(src.height * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    x = (canvas_width - new_w) // 2
    y = (canvas_height - new_h) // 2
    canvas.paste(resized, (x, y), resized)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()


async def render_emoji_to_png(
    hass: HomeAssistant,
    emoji: str,
    canvas_width: int,
    canvas_height: int,
    bg_color: str = "000000",
) -> bytes | None:
    """Render an emoji onto a canvas of the given dimensions.

    Returns PNG bytes ready for make_image_command, or None if the emoji
    could not be fetched.
    """
    codepoint = _emoji_to_codepoint(emoji)
    if not codepoint:
        _LOGGER.warning("Empty emoji codepoint for %r", emoji)
        return None

    png_data = await _fetch_emoji_png(hass, codepoint)
    if png_data is None and "-" in codepoint:
        # Fallback: try first codepoint only (some ZWJ sequences are not in Twemoji)
        first = codepoint.split("-")[0]
        _LOGGER.debug("Falling back to base codepoint %s for emoji %r", first, emoji)
        png_data = await _fetch_emoji_png(hass, first)

    if png_data is None:
        return None

    return await hass.async_add_executor_job(
        _compose_emoji_image, png_data, canvas_width, canvas_height, bg_color
    )
