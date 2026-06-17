"""iPIXEL Color Bluetooth API client - Refactored version."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .bluetooth.client import BluetoothClient
from .device.commands import (
    make_power_command,
    make_brightness_command,
)
from .device.clock import make_clock_mode_command, make_time_command
from .device.text import make_text_command
from .device.image import make_image_command
from .device.info import build_device_info_command, parse_device_response
from .display.text_renderer import inspect_png, render_text_to_png
from .display.weather_clock_renderer import render_weather_clock_to_png
from .exceptions import iPIXELConnectionError
from .const import (
    DEFAULT_DISPLAY_HEIGHT,
    DEFAULT_DISPLAY_WIDTH,
    DISPLAY_SIZE_TO_LED_TYPE,
    LED_TYPE_SPECS,
    NOTIFY_UUID,
    WRITE_UUID,
)

_LOGGER = logging.getLogger(__name__)


class iPIXELAPI:
    """iPIXEL Color device API client - simplified facade."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        display_width: int | None = None,
        display_height: int | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            hass: Home Assistant instance
            address: Bluetooth MAC address
            display_width: Optional manual display width override
            display_height: Optional manual display height override
        """
        self._address = address
        self._bluetooth = BluetoothClient(hass, address)
        self._power_state = False
        self._device_info: dict[str, Any] | None = None
        self._device_response: bytes | None = None
        self._display_width_override = self._normalize_dimension(display_width)
        self._display_height_override = self._normalize_dimension(display_height)
        if self._display_width_override and self._display_height_override:
            _LOGGER.info(
                "Configured display size override for %s: %dx%d",
                self._address,
                self._display_width_override,
                self._display_height_override,
            )
        
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

    async def sync_time(self) -> bool:
        """Sync current time to the device.

        This is useful for keeping the clock display accurate,
        especially after the device has been running for a while.

        Returns:
            True if time was synced successfully
        """
        try:
            time_command = make_time_command()
            success = await self._bluetooth.send_command(time_command)

            if success:
                _LOGGER.debug("Time synchronized to device")
            else:
                _LOGGER.error("Failed to sync time")
            return success

        except Exception as err:
            _LOGGER.error("Error syncing time: %s", err)
            return False

    async def set_clock_mode(
        self,
        style: int = 1,
        date: str = "",
        show_date: bool = True,
        format_24: bool = True
    ) -> bool:
        """Set device to clock display mode.

        Args:
            style: Clock style (0-8)
            date: Date in DD/MM/YYYY format (defaults to today)
            show_date: Whether to show the date
            format_24: Whether to use 24-hour format

        Returns:
            True if command was sent successfully
        """
        try:
            # Set clock mode
            command = make_clock_mode_command(style, date, show_date, format_24)
            success = await self._bluetooth.send_command(command)

            if not success:
                _LOGGER.error("Failed to set clock mode")
                return False

            _LOGGER.info("Clock mode set: style=%d, 24h=%s, show_date=%s",
                       style, format_24, show_date)

            # Sync current time to the device
            time_success = await self.sync_time()
            if not time_success:
                _LOGGER.warning("Clock mode set but time sync failed")

            return success

        except ValueError as err:
            _LOGGER.error("Invalid clock mode parameters: %s", err)
            return False
        except Exception as err:
            _LOGGER.error("Error setting clock mode: %s", err)
            return False
    
    async def get_device_info(self) -> dict[str, Any] | None:
        """Query device information and store it."""
        if self._device_info is not None:
            return self._device_info
            
        try:
            command = build_device_info_command()
            client = self._bluetooth._client
            if client is None:
                raise iPIXELConnectionError("Device not connected")
            
            # Set up notification response
            self._device_response = None
            response_received = asyncio.Event()
            
            def response_handler(sender: Any, data: bytearray) -> None:
                self._device_response = bytes(data)
                response_received.set()
            
            try:
                await client.stop_notify(NOTIFY_UUID)
            except Exception as err:
                _LOGGER.debug("Device info notify stop skipped: %s", err)
            
            try:
                await client.start_notify(NOTIFY_UUID, response_handler)
                _LOGGER.debug(
                    "Requesting device info via %s (%d bytes)",
                    WRITE_UUID,
                    len(command),
                )
                await client.write_gatt_char(WRITE_UUID, command)
                _LOGGER.debug("Device info request write succeeded via %s", WRITE_UUID)
                
                # Wait for response (5 second timeout)
                await asyncio.wait_for(response_received.wait(), timeout=5.0)
                
                if self._device_response:
                    self._device_info = self._apply_display_overrides(
                        parse_device_response(self._device_response),
                        "device response",
                    )
                else:
                    raise Exception("No response received")
                    
            finally:
                try:
                    await client.stop_notify(NOTIFY_UUID)
                except Exception as err:
                    _LOGGER.debug("Device info notify cleanup skipped: %s", err)

                if self._bluetooth._notification_handler:
                    try:
                        await client.start_notify(
                            NOTIFY_UUID,
                            self._bluetooth._notification_handler,
                        )
                    except Exception as err:
                        _LOGGER.warning("Could not restore notification handler: %s", err)
            
            _LOGGER.info(
                "Device info retrieved: type=%s led_type=%s size=%dx%d mcu=%s wifi=%s",
                self._device_info.get("device_type_str"),
                self._device_info.get("led_type"),
                self._device_info.get("width"),
                self._device_info.get("height"),
                self._device_info.get("mcu_version"),
                self._device_info.get("wifi_version"),
            )
            return self._device_info
            
        except Exception as err:
            _LOGGER.error("Failed to get device info: %s", err)
            # Return default values
            self._device_info = self._apply_display_overrides(
                self._build_default_device_info(),
                "fallback",
            )
            _LOGGER.warning(
                "Using device info fallback: type=%s led_type=%s size=%dx%d",
                self._device_info.get("device_type_str"),
                self._device_info.get("led_type"),
                self._device_info.get("width"),
                self._device_info.get("height"),
            )
            return self._device_info
    
    async def display_text(
        self,
        text: str,
        antialias: bool = True,
        font_size: float | None = None,
        font: str | None = None,
        line_spacing: int = 0,
        text_color: str = "ffffff",
        bg_color: str = "000000",
    ) -> bool:
        """Display text as image using PIL and pypixelcolor with color gradient mapping.

        Args:
            text: Text to display (supports multiline with \n)
            antialias: Enable text antialiasing for smoother rendering
            font_size: Fixed font size in pixels (can be fractional), or None for auto-sizing
            font: Font name from fonts/ folder, or None for default
            line_spacing: Additional spacing between lines in pixels
            text_color: Foreground/text color in hex format (e.g., 'ffffff')
            bg_color: Background color in hex format (e.g., '000000')
        """
        try:
            # Get device dimensions
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]
            expected_pixels = width * height

            _LOGGER.debug(
                "Textimage render settings: type=%s led_type=%s size=%dx%d "
                "font=%s font_size=%s line_spacing=%d antialias=%s "
                "text_color=#%s bg_color=#%s",
                device_info.get("device_type_str"),
                device_info.get("led_type"),
                width,
                height,
                font or "OpenSans-Light.ttf",
                f"{font_size:.1f}" if font_size else "auto",
                line_spacing,
                antialias,
                text_color,
                bg_color,
            )

            # Render text to PNG with color gradient
            png_data = render_text_to_png(
                text,
                width,
                height,
                antialias,
                font_size,
                font,
                line_spacing,
                text_color,
                bg_color,
            )
            rendered_width, rendered_height, raw_rgb_length = inspect_png(png_data)

            if (rendered_width, rendered_height) != (width, height):
                _LOGGER.error(
                    "Rendered image size mismatch: expected %dx%d, got %dx%d",
                    width,
                    height,
                    rendered_width,
                    rendered_height,
                )
                return False

            if rendered_width * rendered_height != expected_pixels:
                _LOGGER.error(
                    "Rendered image pixel count mismatch: expected %d, got %d",
                    expected_pixels,
                    rendered_width * rendered_height,
                )
                return False

            _LOGGER.debug(
                "Rendered textimage: size=%dx%d pixels=%d raw_rgb_payload=%d png_payload=%d",
                rendered_width,
                rendered_height,
                expected_pixels,
                raw_rgb_length,
                len(png_data),
            )

            # Generate image commands using pypixelcolor
            commands = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info
            )

            if not commands:
                _LOGGER.error("No BLE image frames generated; aborting textimage upload")
                return False

            total_command_bytes = sum(len(command) for command in commands)
            _LOGGER.debug(
                "Generated textimage BLE payload: frames=%d total_bytes=%d write_char=%s",
                len(commands),
                total_command_bytes,
                WRITE_UUID,
            )

            # Send all command frames
            for i, command in enumerate(commands):
                _LOGGER.debug(
                    "Sending pypixelcolor image frame %d/%d: %d bytes",
                    i + 1,
                    len(commands),
                    len(command)
                )
                success = await self._bluetooth.send_command(command)
                if not success:
                    _LOGGER.error(
                        "Failed to send image frame %d/%d via %s",
                        i + 1,
                        len(commands),
                        WRITE_UUID,
                    )
                    return False
                _LOGGER.debug(
                    "Image frame %d/%d write succeeded via %s",
                    i + 1,
                    len(commands),
                    WRITE_UUID,
                )

            _LOGGER.info(
                "Text rendered as image: '%s' (%dx%d, %d bytes PNG, %d frames)",
                text,
                width,
                height,
                len(png_data),
                len(commands)
            )
            return True

        except Exception as err:
            _LOGGER.error("Error displaying text: %s", err)
            return False

    async def display_text_pypixelcolor(
        self,
        text: str,
        color: str = "ffffff",
        bg_color: str | None = None,
        font: str = "CUSONG",
        animation: int = 0,
        speed: int = 80,
        rainbow_mode: int = 0
    ) -> bool:
        """Display text using pypixelcolor.

        Args:
            text: Text to display (supports emojis)
            color: Text color in hex format (e.g., 'ffffff')
            bg_color: Background color in hex format (e.g., '000000'), or None for transparent
            font: Font name ('CUSONG', 'SIMSUN', 'VCR_OSD_MONO') or file path
            animation: Animation type (0-7)
            speed: Animation speed (0-100)
            rainbow_mode: Rainbow mode (0-9)

        Returns:
            True if text was sent successfully
        """
        try:
            # Get device info for height
            device_info = await self.get_device_info()
            device_height = device_info["height"]

            # Generate text commands using pypixelcolor
            commands = make_text_command(
                text=text,
                color=color,
                bg_color=bg_color,
                font=font,
                animation=animation,
                speed=speed,
                rainbow_mode=rainbow_mode,
                save_slot=0,
                device_height=device_height
            )

            # Send all command frames
            for i, command in enumerate(commands):
                _LOGGER.debug(
                    "Sending pypixelcolor text frame %d/%d: %d bytes",
                    i + 1,
                    len(commands),
                    len(command)
                )
                success = await self._bluetooth.send_command(command)
                if not success:
                    _LOGGER.error("Failed to send text frame %d/%d", i + 1, len(commands))
                    return False

            _LOGGER.info(
                "Pypixelcolor text sent: '%s' (color=%s, bg=%s, font=%s, anim=%d, speed=%d, frames=%d)",
                text,
                color,
                bg_color or "none",
                font,
                animation,
                speed,
                len(commands)
            )
            return True

        except Exception as err:
            _LOGGER.error("Error displaying pypixelcolor text: %s", err)
            return False

    async def display_weather_clock(
        self,
        *,
        condition: str,
        temperature: float | int | None,
        hour_minute: str,
        weekday_index: int,
        day: int,
        month: int,
        custom_text: str | None = None,
        font_name: str = "7x5.ttf",
        font_size: float = 7.5,
    ) -> bool:
        """Display the custom 96x16 weather clock bitmap layout."""
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            _LOGGER.debug(
                "Weather clock render settings: condition=%s temp=%s time=%s "
                "date=%d/%d size=%dx%d font=%s font_size=%.1f",
                condition,
                temperature,
                hour_minute,
                day,
                month,
                width,
                height,
                font_name,
                font_size,
            )

            png_data = render_weather_clock_to_png(
                width=width,
                height=height,
                condition=condition,
                temperature=temperature,
                hour_minute=hour_minute,
                weekday_index=weekday_index,
                day=day,
                month=month,
                custom_text=custom_text,
                font_name=font_name,
                font_size=font_size,
            )
            rendered_width, rendered_height, raw_rgb_length = inspect_png(png_data)
            expected_pixels = width * height

            if (rendered_width, rendered_height) != (width, height):
                _LOGGER.error(
                    "Weather clock image size mismatch: expected %dx%d, got %dx%d",
                    width,
                    height,
                    rendered_width,
                    rendered_height,
                )
                return False

            if raw_rgb_length != expected_pixels * 3:
                _LOGGER.error(
                    "Weather clock payload mismatch: expected %d RGB bytes, got %d",
                    expected_pixels * 3,
                    raw_rgb_length,
                )
                return False

            commands = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
            )

            if not commands:
                _LOGGER.error("No BLE image frames generated for weather clock")
                return False

            _LOGGER.debug(
                "Generated weather clock BLE payload: frames=%d total_bytes=%d "
                "write_char=%s",
                len(commands),
                sum(len(command) for command in commands),
                WRITE_UUID,
            )

            for i, command in enumerate(commands):
                success = await self._bluetooth.send_command(command)
                if not success:
                    _LOGGER.error(
                        "Failed to send weather clock frame %d/%d via %s",
                        i + 1,
                        len(commands),
                        WRITE_UUID,
                    )
                    return False

            _LOGGER.info(
                "Weather clock displayed: %s %s %dx%d",
                condition,
                temperature,
                width,
                height,
            )
            return True

        except Exception as err:
            _LOGGER.error("Error displaying weather clock: %s", err)
            return False

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle notifications from the device."""
        _LOGGER.debug("Notification from %s: %s", sender, data.hex())

    @staticmethod
    def _normalize_dimension(value: int | str | None) -> int | None:
        """Normalize a display dimension override."""
        try:
            dimension = int(value) if value is not None else 0
        except (TypeError, ValueError):
            return None
        return dimension if dimension > 0 else None

    def _build_default_device_info(self) -> dict[str, Any]:
        """Build default device info for devices that do not answer info queries."""
        return {
            "width": DEFAULT_DISPLAY_WIDTH,
            "height": DEFAULT_DISPLAY_HEIGHT,
            "device_type": 131,
            "device_type_str": "Unknown",
            "led_type": 3,
            "mcu_version": "Unknown",
            "wifi_version": "Unknown",
            "has_wifi": False,
            "password_flag": 255,
        }

    def _apply_display_overrides(
        self,
        device_info: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        """Apply configured display size overrides to device info."""
        info = dict(device_info)
        width = self._display_width_override
        height = self._display_height_override

        if bool(width) != bool(height):
            _LOGGER.warning(
                "Ignoring incomplete display size override width=%s height=%s",
                width,
                height,
            )
            return info

        if not width or not height:
            _LOGGER.debug(
                "Detected display from %s: type=%s led_type=%s size=%dx%d",
                source,
                info.get("device_type_str"),
                info.get("led_type"),
                info.get("width"),
                info.get("height"),
            )
            return info

        led_type = DISPLAY_SIZE_TO_LED_TYPE.get((width, height))
        if led_type is not None:
            spec = LED_TYPE_SPECS[led_type]
            info["device_type"] = spec["device_type"]
            info["led_type"] = led_type
            info["device_type_str"] = f"Type {led_type} ({spec['name']}, override)"
        else:
            info["device_type_str"] = f"Unknown ({width}x{height}, override)"

        info["width"] = width
        info["height"] = height
        _LOGGER.info(
            "Applied display size override to %s: type=%s led_type=%s size=%dx%d",
            source,
            info.get("device_type_str"),
            info.get("led_type"),
            width,
            height,
        )
        return info
    
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


# Export at module level for convenience
__all__ = ["iPIXELAPI", "iPIXELError", "iPIXELConnectionError", "iPIXELTimeoutError"]
from .exceptions import iPIXELError, iPIXELConnectionError, iPIXELTimeoutError
