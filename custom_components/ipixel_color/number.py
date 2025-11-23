"""Number entity for iPIXEL Color numeric settings."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color number entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    # Only brightness remains as a separate number entity
    # Font size and line spacing are now part of the style entity
    async_add_entities([
        iPIXELBrightness(api, entry, address, name),
    ])


class iPIXELBrightness(NumberEntity, RestoreEntity):
    """Representation of an iPIXEL Color brightness setting."""

    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = 1  # Minimum brightness (0 is invalid)
    _attr_native_max_value = 100  # Maximum brightness
    _attr_native_step = 1
    _attr_icon = "mdi:brightness-6"
    _attr_entity_category = None

    def __init__(
        self, 
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the brightness number."""
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = f"{name} Brightness"
        self._attr_unique_id = f"{address}_brightness"
        self._attr_native_value = 50  # Default brightness is 50%
        self._attr_entity_description = "Display brightness level (1-100)"
        
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
        if last_state is not None and last_state.state not in ("unknown", "unavailable"):
            try:
                value = int(float(last_state.state))
                if 1 <= value <= 100:
                    self._attr_native_value = value
                    _LOGGER.debug("Restored brightness: %d", self._attr_native_value)
                else:
                    _LOGGER.warning("Invalid brightness value %d, using default 50", value)
                    self._attr_native_value = 50
            except (ValueError, TypeError):
                _LOGGER.warning("Could not restore brightness from: %s", last_state.state)
                self._attr_native_value = 50

    @property
    def native_value(self) -> float | None:
        """Return the current brightness value."""
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the brightness."""
        brightness = int(value)
        if 1 <= brightness <= 100:
            try:
                # Send brightness command to device
                success = await self._api.set_brightness(brightness)
                if success:
                    self._attr_native_value = brightness
                    _LOGGER.info("Brightness set to %d%%", brightness)
                else:
                    _LOGGER.error("Failed to set brightness to %d%%", brightness)
            except Exception as err:
                _LOGGER.error("Error setting brightness: %s", err)
        else:
            _LOGGER.error("Invalid brightness: %d (must be 1-100)", brightness)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True