"""iPIXEL Color Bluetooth API client - Refactored version."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from homeassistant.components import bluetooth

from .bluetooth.client import BluetoothClient
from .device.commands import (
    make_power_command,
    make_brightness_command,
)
from .device.clock import make_clock_mode_command, make_time_command
from .device.text import make_text_command
from .device.image import make_image_command
from .device.info import build_device_info_command, parse_device_response
from .display.text_renderer import render_text_to_png
from .exceptions import iPIXELConnectionError

_LOGGER = logging.getLogger(__name__)

# Reconnect backoff schedule: first attempt after 5s, then 10s, capped at 30s.
RECONNECT_BACKOFF_START = 5.0
RECONNECT_BACKOFF_MAX = 30.0


class iPIXELAPI:
    """iPIXEL Color device API client - simplified facade."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the API client.

        Args:
            hass: Home Assistant instance
            address: Bluetooth MAC address
        """
        self._hass = hass
        self._address = address
        self._bluetooth = BluetoothClient(hass, address)
        self._bluetooth.on_disconnect = self._on_disconnect
        self._power_state = False
        self._device_info: dict[str, Any] | None = None
        self._device_response: bytes | None = None
        # Serializes reconnect attempts and guards the watcher bookkeeping.
        self._reconnect_lock = asyncio.Lock()
        self._reconnect_task: asyncio.Task | None = None
        self._unsubscribe_bluetooth: Callable | None = None
        self._watcher_started = False

    # ------------------------------------------------------------------ lifecycle

    async def connect(self) -> bool:
        """Connect to the iPIXEL device."""
        return await self._bluetooth.connect(self._notification_handler)

    async def disconnect(self) -> None:
        """Disconnect from the device and stop the reconnect watcher."""
        await self.stop_watcher()
        await self._bluetooth.disconnect()

    async def ensure_connected(self) -> bool:
        """Ensure the device link is up, reconnecting if it dropped.

        Reconnect-aware entry point used by entity action paths. Never
        raises; returns True when the device is (or just became) connected.
        """
        return await self._bluetooth.ensure_connected()

    # ------------------------------------------------------------- reconnect logic

    def _on_disconnect(self) -> None:
        """Handle an unexpected link drop (called synchronously by the client).

        Schedules a background reconnect with backoff so the panel recovers
        without a manual integration reload. The watcher also subscribes to
        HA Bluetooth advertisements so a reappearing device is picked up
        immediately instead of waiting for the next poll.
        """
        if not self._watcher_started:
            return
        # The disconnect callback may fire from a non-event-loop thread
        # (bleak's own thread); hop back to the loop before scheduling.
        self._hass.loop.call_soon_threadsafe(self._schedule_reconnect)

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnect loop, unless one is already running."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = self._hass.async_create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnect with backoff until the link is up again."""
        try:
            async with self._reconnect_lock:
                if self.is_connected:
                    return
                delay = RECONNECT_BACKOFF_START
                _LOGGER.warning(
                    "iPIXEL device %s link lost; reconnecting (backoff %.0fs)",
                    self._address,
                    delay,
                )
                while not self.is_connected:
                    await asyncio.sleep(delay)
                    if not self._watcher_started:
                        return
                    if await self.ensure_connected():
                        _LOGGER.info("Reconnected to iPIXEL device %s", self._address)
                        return
                    delay = min(delay * 2, RECONNECT_BACKOFF_MAX)
                    _LOGGER.warning(
                        "Reconnect attempt for %s failed; next in %.0fs",
                        self._address,
                        delay,
                    )
        finally:
            if (
                self._reconnect_task is not None
                and self._reconnect_task is asyncio.current_task()
            ):
                self._reconnect_task = None

    async def start_watcher(self) -> None:
        """Start the reconnect watcher (bluetooth advertisement subscription).

        Called once from async_setup_entry after the initial connection.
        Idempotent; safe to call more than once (e.g. after reconnects).
        """
        if self._watcher_started:
            return
        self._watcher_started = True

        def _advertisement_callback(
            service_info: bluetooth.BluetoothServiceInfoBleak,
            change: bluetooth.BluetoothChange,
        ) -> None:
            # The panel is advertising again; if we are not connected, bring
            # the link back immediately instead of waiting for the backoff.
            if not self.is_connected:
                self._schedule_reconnect()

        self._unsubscribe_bluetooth = bluetooth.async_register_callback(
            self._hass,
            _advertisement_callback,
            {"address": self._address},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    async def stop_watcher(self) -> None:
        """Stop the reconnect watcher and cancel any pending reconnect task."""
        self._watcher_started = False
        if self._unsubscribe_bluetooth is not None:
            try:
                self._unsubscribe_bluetooth()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Error unsubscribing bluetooth callback: %s", err)
            self._unsubscribe_bluetooth = None
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reconnect_task = None

    async def _send_with_reconnect(self, command: bytes) -> bool:
        """Send a command, reconnecting once on a stale connection.

        The first attempt may hit a connection that died between the
        availability check and the write; when that happens, reconnect and
        retry the command once instead of failing the entity action.
        """
        try:
            return await self._bluetooth.send_command(command)
        except iPIXELConnectionError:
            if await self.ensure_connected():
                return await self._bluetooth.send_command(command)
            return False

    # ------------------------------------------------------------------ commands

    async def set_power(self, on: bool) -> bool:
        """Set device power state."""
        command = make_power_command(on)
        success = await self._send_with_reconnect(command)

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
            success = await self._send_with_reconnect(command)

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
            success = await self._send_with_reconnect(time_command)

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
            success = await self._send_with_reconnect(command)

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
        if not await self.ensure_connected():
            _LOGGER.warning("Cannot read device info: %s not connected", self._address)
            return None

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
                "device_type": 0,
                "device_type_str": "Unknown",
                "led_type": 0,
                "mcu_version": "Unknown",
                "wifi_version": "Unknown",
                "has_wifi": False,
                "password_flag": 255
            }
            return self._device_info

    async def display_text(self, text: str, antialias: bool = True, font_size: float | None = None, font: str | None = None, line_spacing: int = 0, text_color: str = "ffffff", bg_color: str = "000000") -> bool:
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

            # Render text to PNG with color gradient
            png_data = render_text_to_png(text, width, height, antialias, font_size, font, line_spacing, text_color, bg_color)

            # Generate image commands using pypixelcolor
            commands = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info
            )

            # Send all command frames
            for i, command in enumerate(commands):
                _LOGGER.debug(
                    "Sending pypixelcolor image frame %d/%d: %d bytes",
                    i + 1,
                    len(commands),
                    len(command)
                )
                success = await self._send_with_reconnect(command)
                if not success:
                    _LOGGER.error("Failed to send image frame %d/%d", i + 1, len(commands))
                    return False

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
                success = await self._send_with_reconnect(command)
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


# Export at module level for convenience
__all__ = ["iPIXELAPI", "iPIXELError", "iPIXELConnectionError", "iPIXELTimeoutError"]
from .exceptions import iPIXELError, iPIXELConnectionError, iPIXELTimeoutError
