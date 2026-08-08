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
from .common import update_ipixel_display

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
        iPIXELSyncTimeButton(hass, api, entry, address, name),
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
        self._attr_name = "Update Display"
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
        await update_ipixel_display(self.hass, self._name, self._api)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class iPIXELSyncTimeButton(ButtonEntity):
    """Representation of an iPIXEL Color time sync button."""

    _attr_icon = "mdi:clock-sync"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the sync time button."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Sync Time"
        self._attr_unique_id = f"{address}_sync_time_button"
        self._attr_entity_description = "Sync current time to device clock"

        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    async def async_press(self) -> None:
        """Handle button press to sync time."""
        _LOGGER.debug("Manual time sync triggered")
        try:
            # Connect if needed (reconnect-aware)
            if not await self._api.ensure_connected():
                _LOGGER.error("Cannot sync time: device %s not connected", self._api.address)
                return

            # Sync time
            success = await self._api.sync_time()

            if success:
                _LOGGER.info("Time synchronized successfully")
            else:
                _LOGGER.error("Failed to sync time")

        except Exception as err:
            _LOGGER.error("Error during time sync: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True