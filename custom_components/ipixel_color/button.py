"""Button entity for iPIXEL Color manual controls."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color button entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELUpdateButton(hass, api, entry, address, name),
    ])


class iPIXELUpdateButton(ButtonEntity):
    """Representation of an iPIXEL Color update button."""

    _attr_icon = "mdi:refresh"

    def __init__(
        self, 
        hass: HomeAssistant,
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the update button."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = f"{name} Update Display"
        self._attr_unique_id = f"{address}_update_button"
        self._attr_entity_description = "Manually update display with current text and settings"
        
        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    async def async_press(self) -> None:
        """Handle button press to update display."""
        _LOGGER.debug("Manual display update triggered")
        
        try:
            # Get current text from text entity
            text = await self._get_current_text()
            if not text:
                _LOGGER.warning("No text to display - skipping update")
                return
            
            # Get font settings from other entities
            font_name = await self._get_font_setting()
            font_size = await self._get_font_size_setting()
            antialias = await self._get_antialiasing_setting()
            
            # Connect if needed
            if not self._api.is_connected:
                _LOGGER.debug("Reconnecting to device for manual update")
                await self._api.connect()
            
            # Send text to display with current settings
            success = await self._api.display_text(text, antialias, font_size, font_name)
            
            if success:
                _LOGGER.info("Manual display update successful: %s (font: %s, size: %s, antialias: %s)", 
                           text, font_name or "Default", 
                           f"{font_size}px" if font_size else "Auto", antialias)
            else:
                _LOGGER.error("Manual display update failed")
                
        except Exception as err:
            _LOGGER.error("Error during manual display update: %s", err)

    async def _get_current_text(self) -> str | None:
        """Get the current text from the text entity."""
        try:
            # Get the text entity
            entity_id = f"text.{self._name.lower().replace(' ', '_')}_display"
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable", ""):
                return state.state
        except Exception as err:
            _LOGGER.debug("Could not get current text: %s", err)
        return None

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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True