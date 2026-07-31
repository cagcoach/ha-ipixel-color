"""Text entity for iPIXEL Color."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI, iPIXELConnectionError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import get_entity_id_by_unique_id
from .common import resolve_template_variables, update_ipixel_display

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color text input."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELTextDisplay(hass, api, entry, address, name),
    ])
    # Actions (send_mdi_icon, send_text, send_layout, etc.) are registered
    # once at integration setup in services.py, not here - see
    # https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/


class iPIXELTextDisplay(TextEntity, RestoreEntity):
    """Representation of an iPIXEL Color text display."""

    _attr_mode = TextMode.TEXT
    _attr_native_max = 500  # Maximum 500 characters per protocol

    def __init__(
        self, 
        hass: HomeAssistant,
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the text display."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Display"
        self._attr_unique_id = f"{address}_text_display"
        self._current_text = ""
        self._available = True
        
        # Store current settings (could be exposed as additional entities later)
        self._effect = "scroll_ltr"  # Default to left-to-right scrolling
        self._speed = 50
        self._color_fg = (255, 255, 255)  # White text
        self._color_bg = (0, 0, 0)  # Black background

        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state:
            self._current_text = last_state.state
            _LOGGER.debug("Restored text state: %s", self._current_text)

    @property
    def native_value(self) -> str | None:
        """Return the current text value."""
        return self._current_text

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Always return True to allow reconnection attempts
        # The actual connection state will be handled in the async_set_value method
        return True

    async def async_set_value(self, value: str) -> None:
        """Set the text to display."""
        try:
            # Store the original text value (preserving \n as typed)
            self._current_text = value
            
            # Check if auto-update is enabled
            auto_update = await self._get_auto_update_setting()
            if not auto_update:
                _LOGGER.debug("Auto-update disabled - text stored but not sent to display. Use update button to refresh.")
                return
            
            # Resolve templates and process escape sequences when sending to display
            template_resolved = await resolve_template_variables(self.hass, value)
            processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')
            
            # Auto-update is enabled, proceed with display update
            await self._update_display(processed_text)
                
        except iPIXELConnectionError as err:
            _LOGGER.error("Connection error while displaying text: %s", err)
            # Don't set unavailable to allow retry
        except Exception as err:
            _LOGGER.error("Unexpected error while displaying text: %s", err)

    async def _update_display(self, text: str | None = None) -> None:
        """Update the physical display with text and current settings.
        
        Args:
            text: Pre-processed text to display, or None to use stored text
        """
        # Use the common update function
        await update_ipixel_display(self.hass, self._name, self._api, text)

    async def _get_auto_update_setting(self) -> bool:
        """Get the current auto-update setting from the switch entity."""
        try:
            # Get the auto-update switch entity
            entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            state = self.hass.states.get(entity_id)
            if state:
                return state.state == "on"
        except Exception as err:
            _LOGGER.debug("Could not get auto-update setting: %s", err)
        return False  # Default to manual updates only

    async def async_send_mdi_icon(
        self,
        icon: str,
        color: tuple[int, int, int] = (255, 255, 255),
        bg_color: tuple[int, int, int] = (0, 0, 0),
        scale: int = 100,
        save_slot: int = 0,
    ) -> None:
        """Render and display a Home Assistant MDI icon (service: send_mdi_icon).

        Args:
            icon: MDI icon name, e.g. 'mdi:battery-outline' or 'battery-outline'.
            color: Icon fill color as an (R, G, B) tuple.
            bg_color: Canvas background color as an (R, G, B) tuple.
            scale: Icon size as a percentage of the panel's smaller dimension (1-100).
            save_slot: If >= 1, saves the icon to that device memory slot.
        """
        color_hex = "".join(f"{c:02x}" for c in color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color)

        success = await self._api.send_mdi_icon(
            icon=icon,
            color=color_hex,
            bg_color=bg_color_hex,
            scale=scale,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send MDI icon '%s'", icon)
            raise HomeAssistantError(f"Failed to send MDI icon '{icon}' - check the logs for details")

    async def async_send_text(
        self,
        text: str,
        color: tuple[int, int, int] = (255, 255, 255),
        bg_color: tuple[int, int, int] | None = None,
        font: str = "CUSONG",
        animation: int = 0,
        speed: int = 80,
        rainbow_mode: int = 0,
    ) -> None:
        """Send text using pypixelcolor's native renderer (service: send_text).

        Independent of the entity's stored text/effect/speed/colors (used by
        the 'Display' text box + auto-update flow) - meant for direct calls
        from automations/scripts with their own parameters each time.

        Args:
            text: Text to display (supports emojis).
            color: Text color as an (R, G, B) tuple.
            bg_color: Background color as an (R, G, B) tuple, or None for transparent.
            font: Built-in font name ('CUSONG', 'SIMSUN', 'VCR_OSD_MONO').
            animation: Animation type (0-7). Note: pypixelcolor itself rejects
                3 and 4 on panels that aren't 32x32, to avoid a device bootloop.
            speed: Animation speed (0-100).
            rainbow_mode: Rainbow color-cycling mode (0-9).
        """
        color_hex = "".join(f"{c:02x}" for c in color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color) if bg_color is not None else None

        success = await self._api.display_text_pypixelcolor(
            text=text,
            color=color_hex,
            bg_color=bg_color_hex,
            font=font,
            animation=animation,
            speed=speed,
            rainbow_mode=rainbow_mode,
        )
        if not success:
            _LOGGER.error("Failed to send text '%s'", text)
            raise HomeAssistantError(f"Failed to send text '{text}' - check the logs for details")

    async def async_send_test_pattern(self) -> None:
        """DIAGNOSTIC ONLY: send a 4-quadrant colored test pattern (service: send_test_pattern).

        Used to empirically determine the logical-buffer-to-physical-panel
        mapping when the device's reported width/height doesn't match the
        panel's real physical shape.
        """
        success = await self._api.send_test_pattern()
        if not success:
            _LOGGER.error("Failed to send test pattern")
            raise HomeAssistantError("Failed to send test pattern - check the logs for details")

    async def async_send_layout(
        self,
        icon: str | None = None,
        icon_x: int = 0,
        icon_y: int = 0,
        icon_size: int | None = None,
        icon_color: tuple[int, int, int] = (255, 255, 255),
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
        text_color: tuple[int, int, int] = (255, 255, 255),
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
        bg_color: tuple[int, int, int] = (0, 0, 0),
        save_slot: int = 0,
    ) -> None:
        """Compose up to 4 icons, an image, and up to 4 texts (service: send_layout).

        All optional; give at least one. Positions are each element's
        top-left corner in device pixels. For a single icon use
        icon/icon_x/...; for more than one (up to 4), use `icons` instead -
        a list of dicts with the same shape (icon, x, y, size, color_hex,
        blink, blink_interval_ms) - which takes priority over the flat
        icon/icon_x/... fields if given. Icons never scroll, but can blink.
        For a single text use text/text_x/...; for more than one (up to
        4), use `texts` instead - a list of dicts with the same shape
        (text, x, y, size, font, color_hex, wrap, align, scroll,
        line_spacing, blink, blink_interval_ms) - which takes priority
        over the flat text/text_x/... fields if given. '\\n' in any text
        always forces a line break; wrap additionally auto-wraps at the
        panel edge (word-wrapping reflows text and doesn't preserve exact
        spacing - leave wrap off if you need leading/trailing/internal
        spaces exactly as given, e.g. for manual alignment); align sets
        left/right/center alignment within the text's own block; scroll
        makes text too wide to fit scroll continuously instead (multiple
        scrolling and/or blinking elements stay in sync with each other).
        """
        icon_color_hex = "".join(f"{c:02x}" for c in icon_color)
        text_color_hex = "".join(f"{c:02x}" for c in text_color)
        bg_color_hex = "".join(f"{c:02x}" for c in bg_color)

        success = await self._api.send_layout(
            icon=icon,
            icon_x=icon_x,
            icon_y=icon_y,
            icon_size=icon_size,
            icon_color=icon_color_hex,
            icon_blink=icon_blink,
            icon_blink_interval_ms=icon_blink_interval_ms,
            icons=icons,
            image_path=image_path,
            image_x=image_x,
            image_y=image_y,
            image_width=image_width,
            image_height=image_height,
            text=text,
            text_x=text_x,
            text_y=text_y,
            text_size=text_size,
            text_font=text_font,
            text_color=text_color_hex,
            text_wrap=text_wrap,
            text_line_spacing=text_line_spacing,
            text_align=text_align,
            text_scroll=text_scroll,
            text_blink=text_blink,
            text_blink_interval_ms=text_blink_interval_ms,
            texts=texts,
            scroll_step=scroll_step,
            scroll_frame_ms=scroll_frame_ms,
            scroll_gap=scroll_gap,
            bg_color=bg_color_hex,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send layout")
            raise HomeAssistantError("Failed to send layout - check the logs for details")

    async def async_send_image_file(
        self,
        file_path: str,
        resize_method: str = "crop",
        save_slot: int = 0,
    ) -> None:
        """Send an existing image or GIF file from disk (service: send_image_file).

        The file must be readable by Home Assistant (e.g. under /config/www/).
        """
        success = await self._api.send_image_file(
            file_path=file_path,
            resize_method=resize_method,
            save_slot=save_slot,
        )
        if not success:
            _LOGGER.error("Failed to send image file '%s'", file_path)
            raise HomeAssistantError(f"Failed to send image file '{file_path}' - check the logs for details")

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            # Check connection status
            if self._api.is_connected:
                self._available = True
            else:
                self._available = False
                _LOGGER.debug("Device not connected, marking as unavailable")
                
        except Exception as err:
            _LOGGER.error("Error updating entity state: %s", err)
            self._available = False


