"""Image display commands using pypixelcolor."""
from __future__ import annotations

from typing import Optional

try:
    from pypixelcolor.commands.send_image import send_image_hex
    from pypixelcolor.lib.transport.send_plan import SendPlan
except ImportError:
    send_image_hex = None
    SendPlan = None


def make_image_command(
    image_bytes: bytes,
    file_extension: str = ".png",
    resize_method: str = "crop",
    device_width: Optional[int] = None,
    device_height: Optional[int] = None
) -> list[bytes]:
    """Build image display command using pypixelcolor.

    Args:
        image_bytes: Raw image data bytes (PNG, GIF, JPEG, etc.)
        file_extension: File extension to indicate image type (default: '.png')
        resize_method: Resize method - 'crop' (default) or 'fit'
                      'crop' will fill the entire target area and crop excess
                      'fit' will fit the entire image with black padding
        device_width: Device width in pixels (for resizing)
        device_height: Device height in pixels (for resizing)

    Returns:
        List of command bytes (one per window/frame)

    Raises:
        ImportError: If pypixelcolor is not available
    """
    if send_image_hex is None:
        raise ImportError("pypixelcolor library is not installed")

    # Convert bytes to hex string for pypixelcolor
    hex_string = image_bytes.hex()

    # Build device_info dict if dimensions provided
    device_info = None
    if device_width is not None and device_height is not None:
        # Create a minimal device info dict for pypixelcolor
        from pypixelcolor.lib.device_info import DeviceInfo
        device_info = DeviceInfo(
            width=device_width,
            height=device_height,
            device_type="Unknown",
            mcu_version="Unknown",
            wifi_version="Unknown"
        )

    # Call pypixelcolor's send_image_hex function
    send_plan = send_image_hex(
        hex_string=hex_string,
        file_extension=file_extension,
        resize_method=resize_method,
        device_info=device_info
    )

    # Extract command bytes from all windows
    commands = []
    for window in send_plan.windows:
        commands.append(window.data)

    return commands
