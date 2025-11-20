"""Number entity for iPIXEL Color numeric settings."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up the iPIXEL Color number entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELFontSize(api, entry, address, name),
    ])


class iPIXELFontSize(NumberEntity):
    """Representation of an iPIXEL Color font size setting."""

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0  # 0 = auto-sizing
    _attr_native_max_value = 64  # Maximum font size for 32x32 display
    _attr_native_step = 1
    _attr_icon = "mdi:format-size"
    _attr_entity_category = None

    def __init__(
        self, 
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the font size number."""
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = f"{name} Font Size"
        self._attr_unique_id = f"{address}_font_size"
        self._attr_native_value = 0  # 0 means auto-sizing
        self._attr_entity_description = "Font size in pixels (0 = auto-sizing to fit display)"
        
        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    @property
    def native_value(self) -> float | None:
        """Return the current font size value."""
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the font size."""
        if self._attr_native_min_value <= value <= self._attr_native_max_value:
            self._attr_native_value = int(value)
            if int(value) == 0:
                _LOGGER.debug("Font size changed to: auto-sizing")
            else:
                _LOGGER.debug("Font size changed to: %d pixels", int(value))
            # Note: The actual font size will be used when text is displayed
        else:
            _LOGGER.error("Invalid font size: %f (min: %f, max: %f)", 
                         value, self._attr_native_min_value, self._attr_native_max_value)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True