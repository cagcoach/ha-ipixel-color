"""Text display commands using pypixelcolor."""
from __future__ import annotations

from typing import Optional

try:
    from pypixelcolor.commands.send_text import send_text
    from pypixelcolor.lib.transport.send_plan import SendPlan
except ImportError:
    send_text = None
    SendPlan = None


def make_text_command(
    text: str,
    color: str = "ffffff",
    bg_color: Optional[str] = None,
    font: str = "CUSONG",
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
        font: Font name ('CUSONG', 'SIMSUN', 'VCR_OSD_MONO') or file path
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
        font=font,
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
