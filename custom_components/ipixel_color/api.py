"""iPIXEL Color Bluetooth API client - Refactored version."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bluetooth.client import BluetoothClient
from .device.commands import (
    make_power_command,
    make_brightness_command,
)
from .device.clock import make_clock_mode_command, make_time_command
from .device.text import make_text_command
from .device.image import make_image_command
from .device.info import build_device_info_command, parse_device_response
from .device.mdi_icon import build_mdi_icon_png
from .device.composer import build_layout_media
from .display.text_renderer import render_text_to_png
from .exceptions import iPIXELConnectionError

try:
    from pypixelcolor.commands.show_slot import show_slot as pypixelcolor_show_slot
except ImportError:
    pypixelcolor_show_slot = None

_LOGGER = logging.getLogger(__name__)


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

            response = await self._bluetooth.send_command_wait_response(command, timeout=5.0)

            if response:
                self._device_info = parse_device_response(response)
            else:
                raise Exception("No response received")
            
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
                success = await self._bluetooth.send_command(command)
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

    async def send_mdi_icon(
        self,
        icon: str,
        color: str = "ffffff",
        bg_color: str = "000000",
        scale: int = 100,
        save_slot: int = 0,
    ) -> bool:
        """Render a Home Assistant MDI icon and display it on the device.

        The icon is downloaded from the jsDelivr CDN mirror of @mdi/svg,
        recolored, rasterized and centered on a canvas matching the
        device's own reported width/height (same convention already used
        by display_text), then sent via pypixelcolor's send_image_hex.

        Args:
            icon: MDI icon name, e.g. 'mdi:battery-outline' or 'battery-outline'.
            color: Icon fill color in hex (with or without '#'), e.g. 'ffffff'.
            bg_color: Canvas background color in hex (with or without '#').
            scale: Icon size as a percentage of the panel's smaller
                dimension (1-100). 100 fills edge to edge on the short side.
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            session = async_get_clientsession(self._hass)
            png_data = await build_mdi_icon_png(
                icon=icon,
                session=session,
                canvas_width=width,
                canvas_height=height,
                color_hex=color,
                bg_color_hex=bg_color,
                scale_percent=scale,
            )

            plan = make_image_command(
                image_bytes=png_data,
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send MDI icon '%s'", icon)
                return False

            _LOGGER.info(
                "MDI icon '%s' sent (%dx%d, %d bytes PNG)",
                icon, width, height, len(png_data),
            )
            return True

        except Exception as err:
            _LOGGER.error("Error sending MDI icon '%s': %s", icon, err)
            return False

    async def send_layout(
        self,
        icon: str | None = None,
        icon_x: int = 0,
        icon_y: int = 0,
        icon_size: int | None = None,
        icon_color: str = "ffffff",
        icon_blink: bool = False,
        icon_blink_interval_ms: int = 500,
        icons: list[dict] | None = None,
        image_path: str | None = None,
        image_x: int = 0,
        image_y: int = 0,
        image_width: int | None = None,
        image_height: int | None = None,
        text: str | None = None,
        text_x: int = 0,
        text_y: int = 0,
        text_size: float = 6,
        text_font: str | None = None,
        text_color: str = "ffffff",
        text_wrap: bool = True,
        text_line_spacing: int = 1,
        text_align: str = "left",
        text_scroll: bool = False,
        text_blink: bool = False,
        text_blink_interval_ms: int = 500,
        texts: list[dict] | None = None,
        scroll_step: int = 2,
        scroll_frame_ms: int = 80,
        scroll_gap: int = 16,
        bg_color: str = "000000",
        save_slot: int = 0,
    ) -> bool:
        """Compose up to 4 MDI icons, an image, and up to 4 text elements, and display it.

        All elements are optional but at least one should be given.
        Positions are the top-left corner of each element, in device pixels.

        For a single icon, use the flat icon/icon_x/... parameters (kept
        for backward compatibility). For more than one icon (up to 4), use
        `icons` instead - a list of dicts, each with the same shape as the
        flat parameters (icon, x, y, size, color_hex), e.g.:
            icons=[
                {"icon": "mdi:weather-sunny", "x": 0, "y": 0, "size": 16},
                {"icon": "mdi:water-percent", "x": 20, "y": 0, "size": 16},
            ]
        If `icons` is given, the flat icon/icon_x/... parameters are ignored.

        For a single text, use the flat text/text_x/... parameters (kept for
        backward compatibility). For more than one text (up to 4), use
        `texts` instead - a list of dicts, each with the same shape as the
        flat parameters (text, x, y, size, font, color_hex, wrap, scroll,
        line_spacing). If `texts` is given, the flat text/text_x/...
        parameters are ignored.

        Args:
            icon: Single MDI icon name, e.g. 'mdi:battery-outline'.
                Ignored if `icons` is given. None to skip.
            icon_x: Icon top-left X position in pixels.
            icon_y: Icon top-left Y position in pixels.
            icon_size: Icon size in pixels (square). Defaults to the panel's
                smaller dimension if not given.
            icon_color: Icon fill color in hex (with or without '#').
            icon_blink: If True, the icon blinks on/off (ignored if
                `icons` is given - set 'blink' per item there instead).
            icon_blink_interval_ms: Milliseconds each blink state (on or
                off) lasts.
            icons: List of up to 4 icon dicts - see above. Takes priority
                over icon/icon_x/... if given. Icons are always static (no
                scrolling).
            image_path: Absolute path to an image/GIF file to insert (only
                its first frame, if animated), readable by Home Assistant
                (e.g. under /config/www/). None to skip.
            image_x: Image top-left X position in pixels.
            image_y: Image top-left Y position in pixels.
            image_width: If given, resize the image to this width.
            image_height: If given, resize the image to this height.
            text: Single text to display (ignored if `texts` is given).
                None to skip. '\n' always forces a line break regardless
                of text_wrap.
            text_x: Text top-left X position in pixels.
            text_y: Text top-left Y position in pixels.
            text_size: Font size in pixels (can be fractional) - scales the
                text dynamically.
            text_font: Bundled font name ('3x5-de', '5x5', '7x5',
                'OpenSans-Light', 'WP7xn'), or None for the smallest bundled font.
            text_color: Text color in hex (with or without '#').
            text_wrap: If True (default), automatically word-wrap text that
                would run past the panel's right edge. If False, only
                explicit '\n' breaks lines.
            text_line_spacing: Extra vertical gap between lines, in pixels.
            text_align: Horizontal alignment within the text's own block:
                'left' (default), 'right', or 'center'. Mainly matters with
                multiple '\\n'-separated lines of different widths.
            text_blink: If True, the text blinks on/off (ignored if
                `texts` is given - set 'blink' per item there instead).
            text_blink_interval_ms: Milliseconds each blink state (on or
                off) lasts.
            text_scroll: If True, text too wide to fit scrolls continuously
                (looping GIF) instead of being clipped. No effect if the
                text already fits. Ignored together with text_wrap - wrap
                takes priority when both would apply to fitting text.
            texts: List of up to 4 text element dicts - see above. Takes
                priority over text/text_x/... if given.
            scroll_step: Pixels moved per animation frame, shared by every
                scrolling text so their loops can stay in sync.
            scroll_frame_ms: Duration of each animation frame, in ms.
            scroll_gap: Blank pixels between consecutive loop passes.
            bg_color: Canvas background color in hex (with or without '#').
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            image_bytes = None
            if image_path:
                image_bytes = await self._hass.async_add_executor_job(Path(image_path).read_bytes)

            if icons is None and icon:
                icons = [{
                    "icon": icon, "x": icon_x, "y": icon_y,
                    "size": icon_size, "color_hex": icon_color,
                    "blink": icon_blink, "blink_interval_ms": icon_blink_interval_ms,
                }]

            if texts is None and text:
                texts = [{
                    "text": text, "x": text_x, "y": text_y, "size": text_size,
                    "font": text_font, "color_hex": text_color, "wrap": text_wrap,
                    "align": text_align, "scroll": text_scroll,
                    "line_spacing": text_line_spacing,
                    "blink": text_blink, "blink_interval_ms": text_blink_interval_ms,
                }]

            session = async_get_clientsession(self._hass)
            png_data, file_ext = await build_layout_media(
                canvas_width=width,
                canvas_height=height,
                session=session,
                bg_color_hex=bg_color,
                icons=icons,
                image_bytes=image_bytes,
                image_x=image_x,
                image_y=image_y,
                image_width=image_width,
                image_height=image_height,
                texts=texts,
                scroll_step=scroll_step,
                scroll_frame_ms=scroll_frame_ms,
                scroll_gap=scroll_gap,
            )

            plan = make_image_command(
                image_bytes=png_data,
                file_extension=file_ext,
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send layout (icons=%s, texts=%s)", icons, texts)
                return False

            _LOGGER.info(
                "Layout sent (%dx%d, n_icons=%d, n_texts=%d)",
                width, height, len(icons or []), len(texts or []),
            )
            return True

        except Exception as err:
            _LOGGER.error("Error sending layout: %s", err)
            return False

    async def send_image_file(
        self,
        file_path: str,
        resize_method: str = "crop",
        save_slot: int = 0,
    ) -> bool:
        """Send an existing image or GIF file (read from disk) to the panel.

        The file must be readable by Home Assistant (e.g. under
        /config/www/), and can be any format pypixelcolor's send_image_hex
        supports (PNG, GIF, JPEG, BMP, TIFF, WEBP, HEIC/HEIF). Animated
        GIFs are sent as-is (frame-by-frame, with their own durations).

        Args:
            file_path: Absolute path to the image/GIF file.
            resize_method: 'crop' (default, fills the panel and crops
                excess) or 'fit' (fits the whole image with black padding).
            save_slot: If >= 1, saves the image to that device memory slot.
        """
        try:
            path = Path(file_path)
            file_bytes = await self._hass.async_add_executor_job(path.read_bytes)

            device_info = await self.get_device_info()

            plan = make_image_command(
                image_bytes=file_bytes,
                file_extension=path.suffix or ".png",
                resize_method=resize_method,
                device_info_dict=device_info,
                save_slot=save_slot,
            )

            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send image file '%s'", file_path)
                return False

            _LOGGER.info("Image file '%s' sent (%d bytes)", file_path, len(file_bytes))
            return True

        except Exception as err:
            _LOGGER.error("Error sending image file '%s': %s", file_path, err)
            return False

    async def send_test_pattern(self) -> bool:
        """DIAGNOSTIC ONLY: send a 4-quadrant colored test pattern.

        Sized to the device's own reported (width, height). Used to
        empirically determine how the logical buffer maps onto the
        physical panel when the two don't match (e.g. device reports
        64x16 but the panel is physically a 32x32 square). Remove once
        the mapping is confirmed and no longer needed.

        Quadrants (in logical buffer space, left/right = width split,
        top/bottom = height split): TL=red, TR=green, BL=blue, BR=yellow.
        """
        try:
            device_info = await self.get_device_info()
            width = device_info["width"]
            height = device_info["height"]

            from PIL import Image
            import io

            img = Image.new("RGB", (width, height))
            px = img.load()
            for y in range(height):
                for x in range(width):
                    left = x < width / 2
                    top = y < height / 2
                    if left and top:
                        px[x, y] = (255, 0, 0)
                    elif not left and top:
                        px[x, y] = (0, 255, 0)
                    elif left and not top:
                        px[x, y] = (0, 0, 255)
                    else:
                        px[x, y] = (255, 255, 0)

            buf = io.BytesIO()
            img.save(buf, format="PNG")

            plan = make_image_command(
                image_bytes=buf.getvalue(),
                file_extension=".png",
                resize_method="crop",
                device_info_dict=device_info,
                save_slot=0,
            )
            success = await self._bluetooth.send_plan(plan, ack_timeout=25.0)
            if not success:
                _LOGGER.error("Failed to send test pattern")
                return False

            if pypixelcolor_show_slot is not None:
                show_plan = pypixelcolor_show_slot(0)
                shown = await self._bluetooth.send_plan(show_plan)
                if not shown:
                    _LOGGER.error("Failed to show_slot(0) after sending test pattern")
                    return False

            _LOGGER.info("Test pattern sent (%dx%d), save_slot=0, shown via slot 0", width, height)
            return True
        except Exception as err:
            _LOGGER.error("Error sending test pattern: %s", err)
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