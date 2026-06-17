"""The iPIXEL Color integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .api import iPIXELAPI, iPIXELConnectionError, iPIXELTimeoutError
from .const import (
    CONF_DISPLAY_HEIGHT,
    CONF_DISPLAY_WIDTH,
    DOMAIN,
    CONF_ADDRESS,
    CONF_NAME,
)

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.TEXT,
    Platform.SENSOR,
    Platform.NUMBER,
]

# Type alias for iPIXEL config entries
SERVICE_DISPLAY_WEATHER_CLOCK = "display_weather_clock"
LEGACY_CONTROL_SUFFIXES = {
    "antialiasing",
    "auto_update",
    "clock_24h",
    "clock_show_date",
    "font_select",
    "mode_select",
    "clock_style_select",
    "font_size",
    "line_spacing",
    "text_animation",
    "text_speed",
    "text_rainbow",
    "update_button",
    "sync_time_button",
    "text_color",
    "background_color",
}

DISPLAY_WEATHER_CLOCK_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id"): vol.Any(str, [str]),
        vol.Optional("device_id"): vol.Any(str, [str]),
        vol.Optional("area_id"): vol.Any(str, [str]),
        vol.Optional("weather_entity", default="weather.forecast_home"): str,
        vol.Optional("custom_text"): str,
        vol.Optional("font_name", default="7x5.ttf"): str,
        vol.Optional("font_size", default=7.5): vol.Coerce(float),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up iPIXEL Color services."""
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iPIXEL Color from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up iPIXEL Color for %s (%s)", name, address)
    
    # Create API instance with hass for Bluetooth proxy support
    display_width = entry.options.get(
        CONF_DISPLAY_WIDTH,
        entry.data.get(CONF_DISPLAY_WIDTH),
    )
    display_height = entry.options.get(
        CONF_DISPLAY_HEIGHT,
        entry.data.get(CONF_DISPLAY_HEIGHT),
    )
    api = iPIXELAPI(
        hass,
        address,
        display_width=display_width,
        display_height=display_height,
    )
    
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
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    _register_services(hass)
    _remove_legacy_control_entities(hass, address)
    
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


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await async_reload_entry(hass, entry)


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_DISPLAY_WEATHER_CLOCK):
        return

    async def async_display_weather_clock(call: ServiceCall) -> None:
        """Render and display the custom weather clock layout."""
        api = _get_api_for_service_call(hass, call.data)
        weather_entity = call.data["weather_entity"]
        weather_state = hass.states.get(weather_entity)
        if weather_state is None:
            _LOGGER.error("Weather entity not found: %s", weather_entity)
            return

        temperature = weather_state.attributes.get("temperature")
        custom_text = call.data.get("custom_text")
        if custom_text is None:
            custom_text = _get_custom_text(hass, api.address)
        now = dt_util.now()

        if not api.is_connected:
            _LOGGER.debug("Reconnecting to device for weather clock update")
            await api.connect()

        success = await api.display_weather_clock(
            condition=weather_state.state,
            temperature=temperature,
            hour_minute=now.strftime("%H:%M"),
            weekday_index=now.weekday(),
            day=now.day,
            month=now.month,
            custom_text=custom_text,
            font_name=call.data["font_name"],
            font_size=call.data["font_size"],
        )
        if not success:
            _LOGGER.error("Weather clock service failed")

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISPLAY_WEATHER_CLOCK,
        async_display_weather_clock,
        schema=DISPLAY_WEATHER_CLOCK_SCHEMA,
    )


def _remove_legacy_control_entities(hass: HomeAssistant, address: str) -> None:
    """Remove old advanced controls from the entity registry."""
    registry = er.async_get(hass)
    for suffix in LEGACY_CONTROL_SUFFIXES:
        unique_id = f"{address}_{suffix}"
        for entity_id, entry in list(registry.entities.items()):
            if entry.platform == DOMAIN and entry.unique_id == unique_id:
                registry.async_remove(entity_id)
                _LOGGER.debug("Removed legacy iPIXEL control entity: %s", entity_id)


def _get_custom_text(hass: HomeAssistant, address: str) -> str | None:
    """Read the custom weather-clock text entity."""
    registry = er.async_get(hass)
    unique_id = f"{address}_text_display"
    for entity_id, entry in registry.entities.items():
        if entry.platform == DOMAIN and entry.unique_id == unique_id:
            state = hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable", ""):
                return state.state
            return None
    return None


def _get_api_for_service_call(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> iPIXELAPI:
    """Resolve API instance from service target data."""
    entity_ids = data.get("entity_id")
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    if entity_ids:
        registry = er.async_get(hass)
        entry = registry.entities.get(entity_ids[0])
        if entry and entry.config_entry_id in hass.data.get(DOMAIN, {}):
            return hass.data[DOMAIN][entry.config_entry_id]
        raise ValueError(f"Could not resolve iPIXEL entity: {entity_ids[0]}")

    device_ids = data.get("device_id")
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    if device_ids:
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_ids[0])
        if device:
            for config_entry_id in device.config_entries:
                if config_entry_id in hass.data.get(DOMAIN, {}):
                    return hass.data[DOMAIN][config_entry_id]
        raise ValueError(f"Could not resolve iPIXEL device: {device_ids[0]}")

    apis = list(hass.data.get(DOMAIN, {}).values())
    if len(apis) == 1:
        return apis[0]

    raise ValueError("Specify entity_id when multiple iPIXEL devices are configured")
