"""Device information management for iPIXEL Color devices."""
from __future__ import annotations

import logging
from typing import Any

from ..const import DEVICE_TYPE_BYTE_TO_LED_TYPE, LED_TYPE_SPECS

try:
    from pypixelcolor.lib.internal_commands import build_get_device_info_command
    from pypixelcolor.lib.device_info import parse_device_info as pypixelcolor_parse_device_info
except ImportError:
    build_get_device_info_command = None
    pypixelcolor_parse_device_info = None

_LOGGER = logging.getLogger(__name__)


def build_device_info_command() -> bytes:
    """Build device info query command using pypixelcolor.

    Returns:
        Command bytes to query device information.

    Raises:
        ImportError: If pypixelcolor is not available.
    """
    if build_get_device_info_command is None:
        raise ImportError("pypixelcolor library is not installed")

    return build_get_device_info_command()


def parse_device_response(response: bytes) -> dict[str, Any]:
    """Parse device info response using pypixelcolor.

    Args:
        response: Raw bytes received from the device.

    Returns:
        Device information as a dict for Home Assistant compatibility.

    Raises:
        ImportError: If pypixelcolor is not available.
        ValueError: If response is invalid.
    """
    if pypixelcolor_parse_device_info is None:
        raise ImportError("pypixelcolor library is not installed")

    _LOGGER.debug("Device response: %s", response.hex())
    _LOGGER.info("Raw device response bytes: %s", [hex(b) for b in response])

    # Use pypixelcolor's parser to get DeviceInfo object
    device_info_obj = pypixelcolor_parse_device_info(response)

    led_type = device_info_obj.led_type
    if led_type is None:
        led_type = DEVICE_TYPE_BYTE_TO_LED_TYPE.get(device_info_obj.device_type)

    spec = LED_TYPE_SPECS.get(led_type)
    width = device_info_obj.width
    height = device_info_obj.height
    device_type_str = "Unknown"
    if spec:
        width = spec["width"]
        height = spec["height"]
        device_type_str = f"Type {led_type} ({spec['name']})"

    # Convert DeviceInfo object to dict for Home Assistant compatibility
    device_info = {
        "width": width,
        "height": height,
        "device_type": device_info_obj.device_type,  # int
        "device_type_str": device_type_str,  # String version for display
        "led_type": led_type,
        "mcu_version": device_info_obj.mcu_version,
        "wifi_version": device_info_obj.wifi_version,
        "has_wifi": device_info_obj.has_wifi,
        "password_flag": device_info_obj.password_flag,
    }

    _LOGGER.info("Parsed device info: %dx%d (Device byte %d, LED Type %s)",
                 device_info["width"], device_info["height"],
                 device_info["device_type"], device_info["led_type"])

    return device_info
