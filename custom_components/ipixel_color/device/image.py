"""Image display commands using pypixelcolor."""
from __future__ import annotations

import logging
from typing import Optional

try:
    from pypixelcolor.commands.send_image import send_image_hex
    from pypixelcolor.lib.transport.send_plan import SendPlan
except ImportError:
    send_image_hex = None
    SendPlan = None

_LOGGER = logging.getLogger(__name__)


def make_image_command(
    image_bytes: bytes,
    file_extension: str = ".png",
    resize_method: str = "crop",
    device_info_dict: Optional[dict] = None
) -> list[bytes]:
    """Build image display command using pypixelcolor.

    Args:
        image_bytes: Raw image data bytes (PNG, GIF, JPEG, etc.)
        file_extension: File extension to indicate image type (default: '.png')
        resize_method: Resize method - 'crop' (default) or 'fit'
                      'crop' will fill the entire target area and crop excess
                      'fit' will fit the entire image with black padding
        device_info_dict: Device information dict from api.get_device_info()

    Returns:
        List of command bytes (one per window/frame)

    Raises:
        ImportError: If pypixelcolor is not available
    """
    if send_image_hex is None:
        raise ImportError("pypixelcolor library is not installed")

    if device_info_dict is not None:
        width = int(device_info_dict["width"])
        height = int(device_info_dict["height"])
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid display dimensions: {width}x{height}")
        _LOGGER.debug(
            "Building image command: input_payload=%d bytes target=%dx%d "
            "pixels=%d device_type=%s led_type=%s",
            len(image_bytes),
            width,
            height,
            width * height,
            device_info_dict.get("device_type"),
            device_info_dict.get("led_type"),
        )
    else:
        _LOGGER.debug(
            "Building image command without device info: input_payload=%d bytes",
            len(image_bytes),
        )

    # Convert bytes to hex string for pypixelcolor
    hex_string = image_bytes.hex()

    # Build device_info object from dict if provided
    device_info = None
    if device_info_dict is not None:
        from pypixelcolor.lib.device_info import DeviceInfo
        device_info = DeviceInfo(
            device_type=device_info_dict.get("device_type", 0),
            mcu_version=device_info_dict.get("mcu_version", "Unknown"),
            wifi_version=device_info_dict.get("wifi_version", "Unknown"),
            width=device_info_dict["width"],
            height=device_info_dict["height"],
            has_wifi=device_info_dict.get("has_wifi", False),
            password_flag=device_info_dict.get("password_flag", 255),
            led_type=device_info_dict.get("led_type", None)
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

    _LOGGER.debug(
        "Built image command payload: frames=%d total_bytes=%d",
        len(commands),
        sum(len(command) for command in commands),
    )

    return commands
