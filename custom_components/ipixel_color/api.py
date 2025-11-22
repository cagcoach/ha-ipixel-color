"""iPIXEL Color Bluetooth API client - Refactored version."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .bluetooth.client import BluetoothClient
from .bluetooth.scanner import discover_ipixel_devices
from .device.commands import (
    make_power_command,
    make_diy_mode_command,
    make_default_mode_command,
    make_png_command,
    make_brightness_command,
)
from .device.info import build_device_info_command, parse_device_response
from .display.text_renderer import render_text_to_png
from .exceptions import iPIXELConnectionError

_LOGGER = logging.getLogger(__name__)


class iPIXELAPI:
    """iPIXEL Color device API client - simplified facade."""

    def __init__(self, address: str) -> None:
        """Initialize the API client."""
        self._address = address
        self._bluetooth = BluetoothClient(address)
        self._power_state = False
        self._device_info: dict[str, Any] | None = None
        self._device_response: bytes | None = None
        
    async def connect(self) -> bool:
        """Connect to the iPIXEL device."""
        return await self._bluetooth.connect(self._notification_handler)
    
    async def disconnect(self) -> None:
        """Disconnect from the device."""
        await self._bluetooth.disconnect()
    
    async def set_power(self, on: bool) -> bool:
        """Set device power state."""
        command = make_power_command(on)
        success = await self._bluetooth.send_command(command)
        
        if success:
            self._power_state = on
            _LOGGER.debug("Power set to %s", "ON" if on else "OFF")
        return success
    
    async def set_brightness(self, brightness: int) -> bool:
        """Set device brightness level.
        
        Args:
            brightness: Brightness level from 1 to 100
            
        Returns:
            True if command was sent successfully
        """
        try:
            command = make_brightness_command(brightness)
            success = await self._bluetooth.send_command(command)
            
            if success:
                _LOGGER.debug("Brightness set to %d", brightness)
            else:
                _LOGGER.error("Failed to set brightness to %d", brightness)
            return success
            
        except ValueError as err:
            _LOGGER.error("Invalid brightness value: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error setting brightness: %s", err)
            return False
    
    async def get_device_info(self) -> dict[str, Any] | None:
        """Query device information and store it."""
        if self._device_info is not None:
            return self._device_info
            
        try:
            command = build_device_info_command()
            
            # Set up notification response
            self._device_response = None
            response_received = asyncio.Event()
            
            def response_handler(sender: Any, data: bytearray) -> None:
                self._device_response = bytes(data)
                response_received.set()
            
            # Enable notifications temporarily
            await self._bluetooth._client.start_notify(
                "0000fa03-0000-1000-8000-00805f9b34fb", response_handler
            )
            
            try:
                # Send command
                await self._bluetooth._client.write_gatt_char(
                    "0000fa02-0000-1000-8000-00805f9b34fb", command
                )
                
                # Wait for response (5 second timeout)
                await asyncio.wait_for(response_received.wait(), timeout=5.0)
                
                if self._device_response:
                    self._device_info = parse_device_response(self._device_response)
                else:
                    raise Exception("No response received")
                    
            finally:
                await self._bluetooth._client.stop_notify(
                    "0000fa03-0000-1000-8000-00805f9b34fb"
                )
            
            _LOGGER.info("Device info retrieved: %s", self._device_info)
            return self._device_info
            
        except Exception as err:
            _LOGGER.error("Failed to get device info: %s", err)
            # Return default values
            self._device_info = {
                "width": 64,
                "height": 16,
                "device_type": "Unknown", 
                "mcu_version": "Unknown",
                "wifi_version": "Unknown"
            }
            return self._device_info
    
    async def display_text(self, text: str, antialias: bool = True, font_size: float | None = None, font: str | None = None, line_spacing: int = 0) -> bool:
        """Display text as image using PIL.
        
        Args:
            text: Text to display (supports multiline with \n)
            antialias: Enable text antialiasing for smoother rendering
            font_size: Fixed font size in pixels (can be fractional), or None for auto-sizing
            font: Font name from fonts/ folder, or None for default
            line_spacing: Additional spacing between lines in pixels
        """
        try:
            # Get device dimensions
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]
            
            # Render text to PNG
            png_data = render_text_to_png(text, width, height, antialias, font_size, font, line_spacing)
            
            # Send as PNG following ipixel-ctrl write_data_png.py
            data_size = len(png_data)
            from zlib import crc32
            data_crc = crc32(png_data) & 0xFFFFFFFF
            
            # 1. First exit program mode and enter default mode
            default_mode_command = make_default_mode_command()
            _LOGGER.debug("Setting default mode to exit slideshow")
            await self._bluetooth.send_command(default_mode_command)
            
            # 2. Enable DIY mode (mode 1 = enter and clear current, show new)
            diy_command = make_diy_mode_command(1)
            _LOGGER.debug("Sending DIY mode command: %s", diy_command.hex())
            diy_success = await self._bluetooth.send_command(diy_command)
            if not diy_success:
                _LOGGER.error("DIY mode command failed")
                return False
            
            # 3. Send PNG command
            command = make_png_command(png_data)
            
            _LOGGER.debug("Sending PNG command: length=%d, data_size=%d", 
                         len(command), data_size)
            _LOGGER.debug("PNG header: %s", command[:20].hex())
            
            success = await self._bluetooth.send_command(command)
            if success:
                _LOGGER.info("PNG sent: %s (%dx%d, %d bytes, CRC: 0x%08x, cmd_len: %d)", 
                           text, width, height, data_size, data_crc, len(command))
            else:
                _LOGGER.error("PNG command failed to send")
            return success
            
        except Exception as err:
            _LOGGER.error("Error displaying text: %s", err)
            return False
    
    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle notifications from the device."""
        _LOGGER.debug("Notification from %s: %s", sender, data.hex())
    
    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._bluetooth.is_connected
    
    @property
    def power_state(self) -> bool:
        """Return current power state."""
        return self._power_state
    
    @property
    def address(self) -> str:
        """Return device address."""
        return self._address


# Export the discovery function at module level for convenience
__all__ = ["iPIXELAPI", "discover_ipixel_devices", "iPIXELError", "iPIXELConnectionError", "iPIXELTimeoutError"]
from .bluetooth.scanner import discover_ipixel_devices
from .exceptions import iPIXELError, iPIXELConnectionError, iPIXELTimeoutError