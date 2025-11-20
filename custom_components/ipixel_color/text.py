"""Text entity for iPIXEL Color."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .api import iPIXELAPI, iPIXELConnectionError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

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
    
    async_add_entities([iPIXELTextDisplay(hass, api, entry, address, name)])


class iPIXELTextDisplay(TextEntity):
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
            # Always update the current text value
            self._current_text = value
            
            # Check if auto-update is enabled
            auto_update = await self._get_auto_update_setting()
            if not auto_update:
                _LOGGER.debug("Auto-update disabled - text stored but not sent to display. Use update button to refresh.")
                return
            
            # Auto-update is enabled, proceed with display update
            await self._update_display(value)
                
        except iPIXELConnectionError as err:
            _LOGGER.error("Connection error while displaying text: %s", err)
            # Don't set unavailable to allow retry
        except Exception as err:
            _LOGGER.error("Unexpected error while displaying text: %s", err)

    async def _update_display(self, text: str) -> None:
        """Update the physical display with text and current settings."""
        if not self._api.is_connected:
            _LOGGER.debug("Reconnecting to device before displaying text")
            await self._api.connect()
        
        # Get font settings from other entities
        font_name = await self._get_font_setting()
        font_size = await self._get_font_size_setting()
        antialias = await self._get_antialiasing_setting()
        
        # Send text to display with settings
        success = await self._api.display_text(text, antialias, font_size, font_name)
        
        if success:
            _LOGGER.debug("Successfully displayed text: %s (font: %s, size: %s, antialias: %s)", 
                        text, font_name or "Default", 
                        f"{font_size}px" if font_size else "Auto", antialias)
        else:
            _LOGGER.error("Failed to display text on iPIXEL")

    async def _get_font_setting(self) -> str | None:
        """Get the current font setting from the font select entity."""
        try:
            # Get the font select entity
            entity_id = f"select.{self._name.lower().replace(' ', '_')}_font"
            state = self.hass.states.get(entity_id)
            if state and state.state != "Default":
                return state.state
        except Exception as err:
            _LOGGER.debug("Could not get font setting: %s", err)
        return None

    async def _get_font_size_setting(self) -> int | None:
        """Get the current font size setting from the number entity."""
        try:
            # Get the font size number entity
            entity_id = f"number.{self._name.lower().replace(' ', '_')}_font_size"
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable", ""):
                size_value = int(float(state.state))
                # Return None for 0 (auto-sizing), otherwise return the size
                return None if size_value == 0 else size_value
        except Exception as err:
            _LOGGER.debug("Could not get font size setting: %s", err)
        return None

    async def _get_antialiasing_setting(self) -> bool:
        """Get the current antialiasing setting from the switch entity."""
        try:
            # Get the antialiasing switch entity
            entity_id = f"switch.{self._name.lower().replace(' ', '_')}_antialiasing"
            state = self.hass.states.get(entity_id)
            if state:
                return state.state == "on"
        except Exception as err:
            _LOGGER.debug("Could not get antialiasing setting: %s", err)
        return True  # Default to antialiasing enabled

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