"""Config flow for iPIXEL Color integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import iPIXELAPI, iPIXELConnectionError, iPIXELTimeoutError
from .bluetooth.scanner import discover_ipixel_devices_ha
from .const import (
    CONF_DISPLAY_HEIGHT,
    CONF_DISPLAY_WIDTH,
    DEFAULT_DISPLAY_HEIGHT,
    DEFAULT_DISPLAY_WIDTH,
    DOMAIN,
    CONF_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAddress(HomeAssistantError):
    """Error to indicate there is invalid address."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    address = data[CONF_ADDRESS]

    # Create API instance with hass for Bluetooth proxy support
    api = iPIXELAPI(hass, address)
    
    try:
        # Test connection
        if not await api.connect():
            raise CannotConnect
        
        # Disconnect after successful test
        await api.disconnect()
        
    except iPIXELTimeoutError as err:
        raise CannotConnect from err
    except iPIXELConnectionError as err:
        raise CannotConnect from err
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": f"iPIXEL {address[-8:]}", "address": address}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iPIXEL Color."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> iPIXELOptionsFlowHandler:
        """Create the options flow."""
        return iPIXELOptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize config flow."""
        self._discovered_devices: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return await self._show_discovery_form()

        return await self._handle_device_selection(user_input)

    async def _show_discovery_form(self) -> FlowResult:
        """Show the discovery form with found devices."""
        errors = {}
        
        # Discover devices using HA's bluetooth API
        try:
            _LOGGER.debug("CONFIG_FLOW: Starting device discovery using HA bluetooth API")
            discovered = discover_ipixel_devices_ha(self.hass, return_all=True)
            _LOGGER.debug("CONFIG_FLOW: Discovery returned %d devices", len(discovered))
            self._discovered_devices = {
                device["address"]: device for device in discovered
            }
            _LOGGER.debug("CONFIG_FLOW: Stored %d devices in _discovered_devices", len(self._discovered_devices))
        except Exception as err:
            _LOGGER.error("CONFIG_FLOW: Discovery failed: %s", err)
            import traceback
            _LOGGER.error("CONFIG_FLOW: Traceback: %s", traceback.format_exc())
            errors["base"] = "discovery_failed"

        if not self._discovered_devices and not errors:
            errors["base"] = "no_devices_found"

        # Create device selection list with star indicators for compatible devices
        # Sort devices: compatible (starred) devices first, then others
        compatible_devices = []
        other_devices = []
        
        for address, device in self._discovered_devices.items():
            if device.get("is_compatible", False):
                compatible_devices.append((address, device))
            else:
                other_devices.append((address, device))
        
        # Sort each group by name for consistent ordering
        compatible_devices.sort(key=lambda x: x[1]['name'])
        other_devices.sort(key=lambda x: x[1]['name'])
        
        device_options = {}
        # Add compatible devices first with stars
        for address, device in compatible_devices:
            device_options[address] = f"⭐ {device['name']} ({address})"
        
        # Add other devices without stars
        for address, device in other_devices:
            device_options[address] = f"{device['name']} ({address})"
        
        # Add manual entry option
        device_options["manual"] = "Manual entry"

        data_schema = vol.Schema({
            vol.Required("device"): vol.In(device_options)
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "device_count": str(len(self._discovered_devices))
            },
        )

    async def _handle_device_selection(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle device selection from discovery."""
        selected = user_input["device"]
        
        if selected == "manual":
            return await self.async_step_manual()
        
        # Use discovered device
        device_info = self._discovered_devices.get(selected)
        if not device_info:
            return self.async_abort(reason="device_not_found")
        
        # Validate connection
        errors = {}
        try:
            info = await validate_input(
                self.hass, 
                {
                    CONF_ADDRESS: device_info["address"],
                    CONF_NAME: device_info["name"]
                }
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAddress:
            errors["base"] = "invalid_address"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        
        if errors:
            return await self._show_discovery_form()

        # Check if already configured
        await self.async_set_unique_id(device_info["address"])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info["title"],
            data={
                CONF_ADDRESS: device_info["address"],
                CONF_NAME: device_info["name"],
            },
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual device entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default="iPIXEL Display"): str,
                    **_display_override_schema(),
                }),
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAddress:
            errors["base"] = "invalid_address"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(user_input[CONF_ADDRESS])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=info["title"], 
                data=_clean_display_overrides(user_input)
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default=user_input.get(CONF_ADDRESS, "")): str,
                vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, "iPIXEL Display")): str,
                **_display_override_schema(
                    user_input.get(CONF_DISPLAY_WIDTH, 0),
                    user_input.get(CONF_DISPLAY_HEIGHT, 0),
                ),
            }),
            errors=errors,
        )

    async def async_step_bluetooth(self, discovery_info) -> FlowResult:
        """Handle Bluetooth discovery."""
        address = discovery_info.address
        name = discovery_info.name or f"iPIXEL {address[-8:]}"
        
        # Check if already configured
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        
        # Set context for confirm step
        self.context["title_placeholders"] = {
            "name": name,
            "address": address,
        }
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm Bluetooth discovery."""
        placeholders = self.context["title_placeholders"]
        
        if user_input is not None:
            try:
                # Test connection
                await validate_input(
                    self.hass,
                    {
                        CONF_ADDRESS: placeholders["address"],
                        CONF_NAME: placeholders["name"]
                    }
                )
            except CannotConnect:
                return self.async_abort(reason="cannot_connect")
            except Exception:
                _LOGGER.exception("Unexpected exception during Bluetooth confirm")
                return self.async_abort(reason="unknown")
            
            return self.async_create_entry(
                title=placeholders["name"],
                data={
                    CONF_ADDRESS: placeholders["address"],
                    CONF_NAME: placeholders["name"],
                },
            )

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
        )


class iPIXELOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for iPIXEL Color."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage display size overrides."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data=_clean_display_overrides(user_input),
            )

        current_width = self._config_entry.options.get(
            CONF_DISPLAY_WIDTH,
            self._config_entry.data.get(CONF_DISPLAY_WIDTH, 0),
        )
        current_height = self._config_entry.options.get(
            CONF_DISPLAY_HEIGHT,
            self._config_entry.data.get(CONF_DISPLAY_HEIGHT, 0),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                **_display_override_schema(current_width, current_height),
            }),
            description_placeholders={
                "default_width": str(DEFAULT_DISPLAY_WIDTH),
                "default_height": str(DEFAULT_DISPLAY_HEIGHT),
            },
        )


def _display_override_schema(
    width: int = 0,
    height: int = 0,
) -> dict[Any, Any]:
    """Return schema fields for display size overrides."""
    return {
        vol.Optional(CONF_DISPLAY_WIDTH, default=width): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=512),
        ),
        vol.Optional(CONF_DISPLAY_HEIGHT, default=height): vol.All(
            vol.Coerce(int),
            vol.Range(min=0, max=128),
        ),
    }


def _clean_display_overrides(data: dict[str, Any]) -> dict[str, Any]:
    """Return data with empty display overrides removed."""
    cleaned = dict(data)
    width = int(cleaned.get(CONF_DISPLAY_WIDTH) or 0)
    height = int(cleaned.get(CONF_DISPLAY_HEIGHT) or 0)

    if width > 0 and height > 0:
        cleaned[CONF_DISPLAY_WIDTH] = width
        cleaned[CONF_DISPLAY_HEIGHT] = height
    else:
        cleaned.pop(CONF_DISPLAY_WIDTH, None)
        cleaned.pop(CONF_DISPLAY_HEIGHT, None)

    return cleaned
