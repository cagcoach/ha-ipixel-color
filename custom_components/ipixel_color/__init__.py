"""The iPIXEL Color integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import iPIXELAPI, iPIXELConnectionError, iPIXELTimeoutError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.TEXT, Platform.SENSOR, Platform.SELECT, Platform.NUMBER, Platform.BUTTON]

# Type alias for iPIXEL config entries


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iPIXEL Color from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up iPIXEL Color for %s (%s)", name, address)
    
    # Create API instance
    api = iPIXELAPI(address)
    
    # Test connection
    try:
        if not await api.connect():
            raise ConfigEntryNotReady(f"Failed to connect to iPIXEL device at {address}")
        
        _LOGGER.info("Successfully connected to iPIXEL device %s", address)
        
        # Get device info for sensors
        await api.get_device_info()
        
    except iPIXELTimeoutError as err:
        _LOGGER.error("Connection timeout to iPIXEL device %s: %s", address, err)
        raise ConfigEntryNotReady(f"Connection timeout: {err}") from err
        
    except iPIXELConnectionError as err:
        _LOGGER.error("Failed to connect to iPIXEL device %s: %s", address, err)
        raise ConfigEntryNotReady(f"Connection failed: {err}") from err
    
    # Store API instance in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = api
    entry.runtime_data = api
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading iPIXEL Color integration")
    
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Disconnect from device
        api: iPIXELAPI = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await api.disconnect()
            _LOGGER.debug("Disconnected from iPIXEL device")
        except Exception as err:
            _LOGGER.error("Error disconnecting from device: %s", err)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)