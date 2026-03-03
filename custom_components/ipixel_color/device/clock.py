"""Clock mode commands for iPIXEL Color devices using pypixelcolor."""
from __future__ import annotations

from typing import Optional
import datetime
import homeassistant.util.dt as dt_util

try:
    from pypixelcolor.commands.set_clock_mode import set_clock_mode
    from pypixelcolor.commands.set_time import set_time
except ImportError:
    # Fallback if pypixelcolor is not installed yet
    set_clock_mode = None
    set_time = None


def make_clock_mode_command(
    style: int = 1,
    date: str = "",
    show_date: bool = True,
    format_24: bool = True
) -> bytes:
    """Build clock mode command using pypixelcolor.

    Sets the device to clock display mode with customizable style and format.

    Args:
        style: Clock style (0-8). Different visual styles for the clock display.
        date: Date to display in DD/MM/YYYY format. Defaults to today's date.
        show_date: Whether to show the date alongside the time.
        format_24: Whether to use 24-hour format (True) or 12-hour format (False).

    Returns:
        Command bytes for clock mode.

    Raises:
        ValueError: If parameters are out of valid ranges.
        ImportError: If pypixelcolor is not available.
    """
    if set_clock_mode is None:
        raise ImportError("pypixelcolor library is not installed")

    # Call pypixelcolor's set_clock_mode function
    # It returns a SendPlan object with windows containing the command data
    send_plan = set_clock_mode(
        style=style,
        date=date,
        show_date=show_date,
        format_24=format_24
    )

    # Extract the command bytes from the first (and only) window
    if send_plan.windows and len(list(send_plan.windows)) > 0:
        first_window = next(iter(send_plan.windows))
        return first_window.data
    else:
        raise ValueError("pypixelcolor returned empty SendPlan")


def make_time_command(
    hour: Optional[int] = None,
    minute: Optional[int] = None,
    second: Optional[int] = None
) -> bytes:
    """Build time sync command using pypixelcolor with local time.

    Sends the current time to the device to keep the clock synchronized.
    Uses Home Assistant's local time if no parameters provided.

    Args:
        hour: Hour to set (0-23). If None, uses current hour.
        minute: Minute to set (0-59). If None, uses current minute.
        second: Second to set (0-59). If None, uses current second.

    Returns:
        Command bytes for setting time.

    Raises:
        ValueError: If time parameters are out of valid ranges.
        ImportError: If pypixelcolor is not available.
    """
    if set_time is None:
        raise ImportError("pypixelcolor library is not installed")

    # If any of the time components are None, get the current local time from Home Assistant
    if hour is None or minute is None or second is None:
        # Get the current local time using Home Assistant's utility function
        now = dt_util.now()
        hour = now.hour
        minute = now.minute
        second = now.second

    # Call pypixelcolor's set_time function
    send_plan = set_time(hour=hour, minute=minute, second=second)

    # Extract the command bytes from the first (and only) window
    if send_plan.windows and len(list(send_plan.windows)) > 0:
        first_window = next(iter(send_plan.windows))
        return first_window.data

    raise ValueError("pypixelcolor returned empty SendPlan")
