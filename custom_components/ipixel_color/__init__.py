"""The iPIXEL Color integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .api import iPIXELAPI, iPIXELConnectionError, iPIXELTimeoutError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.TEXT, Platform.SENSOR, Platform.SELECT, Platform.NUMBER, Platform.BUTTON, Platform.LIGHT]

SERVICE_SHOW_EMOJI = "show_emoji"

SHOW_EMOJI_SCHEMA = vol.Schema(
    {
        vol.Required("emoji"): vol.All(str, vol.Length(min=1)),
        vol.Optional("device_id"): vol.Any(None, str, [str]),
        vol.Optional("bg_color"): vol.All(
            [vol.All(int, vol.Range(min=0, max=255))], vol.Length(min=3, max=3)
        ),
        vol.Optional("width"): vol.All(int, vol.Range(min=1, max=512)),
        vol.Optional("height"): vol.All(int, vol.Range(min=1, max=512)),
    }
)


def _resolve_api(hass: HomeAssistant, call: ServiceCall) -> iPIXELAPI:
    """Resolve which iPIXEL API instance to use from a service call."""
    apis: dict[str, iPIXELAPI] = hass.data.get(DOMAIN, {})
    if not apis:
        raise HomeAssistantError("No iPIXEL devices are configured")

    raw = call.data.get("device_id")
    if not raw:
        target = getattr(call, "target", None) or {}
        raw = target.get("device_id") if isinstance(target, dict) else None
    target_device_ids = [raw] if isinstance(raw, str) else (raw or [])

    if not target_device_ids:
        if len(apis) == 1:
            return next(iter(apis.values()))
        raise HomeAssistantError(
            "Multiple iPIXEL devices configured — specify a device_id"
        )

    device_reg = dr.async_get(hass)
    for device_id in target_device_ids:
        device = device_reg.async_get(device_id)
        if not device:
            continue
        for entry_id in device.config_entries:
            if entry_id in apis:
                return apis[entry_id]

    raise HomeAssistantError(f"No iPIXEL device matched {target_device_ids}")


async def _handle_show_emoji(hass: HomeAssistant, call: ServiceCall) -> None:
    api = _resolve_api(hass, call)
    emoji = call.data["emoji"]
    bg_rgb = call.data.get("bg_color")
    bg_color = "{:02x}{:02x}{:02x}".format(*bg_rgb) if bg_rgb else "000000"
    await api.display_emoji(
        emoji,
        bg_color=bg_color,
        width_override=call.data.get("width"),
        height_override=call.data.get("height"),
    )

# Type alias for iPIXEL config entries


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iPIXEL Color from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up iPIXEL Color for %s (%s)", name, address)
    
    # Create API instance with hass for Bluetooth proxy support
    api = iPIXELAPI(hass, address)
    
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

    # Register integration services once (first entry to load)
    if not hass.services.has_service(DOMAIN, SERVICE_SHOW_EMOJI):
        async def _show_emoji_service(call: ServiceCall) -> None:
            await _handle_show_emoji(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_SHOW_EMOJI,
            _show_emoji_service,
            schema=SHOW_EMOJI_SCHEMA,
        )

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