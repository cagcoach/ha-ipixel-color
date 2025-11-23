"""iPIXEL Color style control platform for unified style management."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .style_control import iPIXELStyleControl
from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iPIXEL Color style control entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    api = hass.data[DOMAIN][entry.entry_id]
    
    # Add the style control entity
    async_add_entities([iPIXELStyleControl(hass, api, entry, address, name)])
    
    # Register the set_style service
    platform = hass.data.get("entity_platform")
    if platform is not None:
        platform.async_register_entity_service(
            "set_style",
            {
                "font": str,
                "font_size": float,
                "antialias": bool,
                "line_spacing": int,
                "preset": str,
            },
            "async_set_style",
        )