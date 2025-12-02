"""Text entity for iPIXEL Color."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI, iPIXELConnectionError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import resolve_template_variables, update_ipixel_display
from .color import iPIXELColorBase

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
        iPIXELTextColor(hass, api, entry, address, name),
        iPIXELBackgroundColor(hass, api, entry, address, name),
    ])


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
        self._attr_name = f"{name} Display"
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
            entity_id = f"switch.{self._name.lower().replace(' ', '_')}_auto_update"
            state = self.hass.states.get(entity_id)
            if state:
                return state.state == "on"
        except Exception as err:
            _LOGGER.debug("Could not get auto-update setting: %s", err)
        return False  # Default to manual updates only

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


class iPIXELTextColor(iPIXELColorBase):
    """Representation of an iPIXEL Color text/foreground color setting."""

    _color_name = "Text Color"
    _entity_suffix = "text_color"
    _default_color = "ffffff"  # White
    _trigger_modes = ["text", "textimage"]  # Trigger update in both text and textimage modes


class iPIXELBackgroundColor(iPIXELColorBase):
    """Representation of an iPIXEL Color background color setting."""

    _color_name = "Background Color"
    _entity_suffix = "background_color"
    _default_color = "000000"  # Black
    _trigger_modes = ["textimage"]  # Trigger update only in textimage mode