"""Text display commands using pypixelcolor."""
from __future__ import annotations

from typing import Optional

import json
import logging
from pathlib import Path
from typing import Any, Union

try:
    from pypixelcolor.commands.send_text import send_text
    from pypixelcolor.lib.font_config import FontConfig
    from pypixelcolor.lib.transport.send_plan import SendPlan
except ImportError:
    send_text = None
    FontConfig = None
    SendPlan = None

_LOGGER = logging.getLogger(__name__)

# pypixelcolor's built-in font since 0.5.0 (GNU Unifont, OFL 1.1).
BUILTIN_FONT = "UNIFONT"

# Metrics used for a font file that has no sidecar JSON. Same values
# pypixelcolor 0.4 used, so fonts without a JSON render as they did before.
_DEFAULT_PIXEL_THRESHOLD = 70


def _sidecar_metrics(font_path: Path, char_height: int) -> dict[str, Any] | None:
    """Return the sidecar JSON metrics closest to char_height, if any.

    pypixelcolor 0.4 read ``<font>.json`` next to the font file, with metrics
    per character height; 0.5 dropped that, so the integration reads it here.
    """
    json_path = font_path.with_suffix(".json")
    if not json_path.is_file():
        return None
    try:
        config = json.loads(json_path.read_text(encoding="utf-8"))
        metrics = {int(h): m for h, m in config["metrics"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as err:
        _LOGGER.warning("Ignoring invalid font metrics %s: %s", json_path, err)
        return None
    if not metrics:
        return None
    closest = min(metrics, key=lambda h: abs(h - char_height))
    chosen = metrics[closest]
    if not isinstance(chosen, dict):
        _LOGGER.warning("Ignoring invalid font metrics for height %s in %s", closest, json_path)
        return None
    return chosen


def _is_builtin_font_file(path: Path) -> bool:
    """True for pypixelcolor's own Unifont file, which it tunes itself."""
    try:
        from pypixelcolor.lib.font_config import UNIFONT_PATH
    except ImportError:
        return False
    return path.resolve() == Path(UNIFONT_PATH).resolve()


def resolve_text_font(font: str | None, char_height: int) -> Union[str, Any]:
    """Turn a font name or file path into what pypixelcolor 0.5 expects.

    Returns the built-in font name for anything that is not an existing file,
    otherwise a FontConfig carrying the font's sidecar metrics. Does file I/O,
    so call it from an executor.
    """
    if not font or FontConfig is None:
        return BUILTIN_FONT
    path = Path(font)
    if not path.is_file() or _is_builtin_font_file(path):
        return BUILTIN_FONT
    metrics = _sidecar_metrics(path, char_height) or {}
    offset = metrics.get("offset", (0, 0))
    try:
        return FontConfig.from_file(
            path,
            font_size=int(metrics.get("font_size", char_height)),
            offset=(int(offset[0]), int(offset[1])),
            pixel_threshold=int(metrics.get("pixel_threshold", _DEFAULT_PIXEL_THRESHOLD)),
            var_width=bool(metrics.get("var_width", False)),
        )
    except (OSError, ValueError, TypeError, IndexError) as err:
        _LOGGER.warning("Could not load font %s, using %s: %s", font, BUILTIN_FONT, err)
        return BUILTIN_FONT


def make_text_command(
    text: str,
    color: str = "ffffff",
    bg_color: Optional[str] = None,
    font: str = BUILTIN_FONT,
    animation: int = 0,
    speed: int = 80,
    rainbow_mode: int = 0,
    save_slot: int = 0,
    char_height: Optional[int] = None
) -> list[bytes]:
    """Build text display command using pypixelcolor.

    Args:
        text: The text to display
        color: Text color in hex format (e.g., 'ffffff')
        bg_color: Background color in hex format (e.g., '000000'), or None for transparent
        font: Font file path, or None/'UNIFONT' for pypixelcolor's built-in font
        animation: Animation type (0-7, excluding 3&4 on non-32x32 devices)
        speed: Animation speed (0-100)
        rainbow_mode: Rainbow mode (0-9)
        save_slot: Save slot (0-255)
        char_height: Character height in pixels (auto-detected if None)

    Returns:
        List of command bytes (one per window/frame)

    Raises:
        ImportError: If pypixelcolor is not available
        ValueError: If parameters are out of valid ranges
    """
    if send_text is None:
        raise ImportError("pypixelcolor library is not installed")

    # Call pypixelcolor's send_text function
    send_plan = send_text(
        text=text,
        color=color,
        bg_color=bg_color,
        font=resolve_text_font(font, char_height or 16),
        animation=animation,
        speed=speed,
        rainbow_mode=rainbow_mode,
        save_slot=save_slot,
        char_height=char_height
    )

    # Extract command bytes from all windows
    # send_text may return multiple windows for large text
    commands = []
    for window in send_plan.windows:
        commands.append(window.data)

    return commands
