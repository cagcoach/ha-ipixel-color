"""Switch platform for iPIXEL Color."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI, iPIXELConnectionError
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import get_entity_id_by_unique_id
from .common import update_ipixel_display

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color switch."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELSwitch(api, entry, address, name),
    ])


class iPIXELSwitch(SwitchEntity):
    """Representation of an iPIXEL Color switch."""

    def __init__(
        self, 
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the switch."""
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = name
        self._attr_unique_id = f"{address}_power"
        self._is_on = False
        self._available = True

        # Device info for grouping in device registry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Always return True to allow reconnection attempts
        # The actual connection state will be handled in the turn_on/turn_off methods
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        try:
            if not self._api.is_connected:
                _LOGGER.debug("Reconnecting to device before turning on")
                await self._api.connect()
            
            success = await self._api.set_power(True)
            if success:
                self._is_on = True
                _LOGGER.debug("Successfully turned on iPIXEL display")
            else:
                _LOGGER.error("Failed to turn on iPIXEL display")
                
        except iPIXELConnectionError as err:
            _LOGGER.error("Connection error while turning on: %s", err)
            # Don't set unavailable to allow retry
        except Exception as err:
            _LOGGER.error("Unexpected error while turning on: %s", err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        try:
            if not self._api.is_connected:
                _LOGGER.debug("Reconnecting to device before turning off")
                await self._api.connect()
            
            success = await self._api.set_power(False)
            if success:
                self._is_on = False
                _LOGGER.debug("Successfully turned off iPIXEL display")
            else:
                _LOGGER.error("Failed to turn off iPIXEL display")
                
        except iPIXELConnectionError as err:
            _LOGGER.error("Connection error while turning off: %s", err)
            # Don't set unavailable to allow retry
        except Exception as err:
            _LOGGER.error("Unexpected error while turning off: %s", err)

    async def async_update(self) -> None:
        """Update the entity state."""
        try:
            # Check connection status
            if self._api.is_connected:
                self._available = True
                # In this basic version, we use the API's cached power state
                self._is_on = self._api.power_state
            else:
                self._available = False
                _LOGGER.debug("Device not connected, marking as unavailable")
                
        except Exception as err:
            _LOGGER.error("Error updating entity state: %s", err)
            self._available = False


class iPIXELAntialiasingSwitch(SwitchEntity, RestoreEntity):
    """Representation of an iPIXEL Color antialiasing setting."""

    _attr_icon = "mdi:vector-selection"

    def __init__(
        self, 
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the antialiasing switch."""
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Antialiasing"
        self._attr_unique_id = f"{address}_antialiasing"
        self._attr_entity_description = "Enable text antialiasing for smooth text (disable for sharp pixels)"
        self._is_on = True  # Default to antialiasing enabled

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
        if last_state is not None:
            self._is_on = last_state.state == "on"
            _LOGGER.debug("Restored antialiasing state: %s", self._is_on)

    @property
    def is_on(self) -> bool:
        """Return True if antialiasing is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable antialiasing."""
        self._is_on = True
        _LOGGER.debug("Antialiasing enabled")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable antialiasing."""
        self._is_on = False
        _LOGGER.debug("Antialiasing disabled")


class iPIXELAutoUpdateSwitch(SwitchEntity, RestoreEntity):
    """Representation of an iPIXEL Color auto-update setting."""

    _attr_icon = "mdi:auto-fix"

    def __init__(
        self, 
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the auto-update switch."""
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Auto Update"
        self._attr_unique_id = f"{address}_auto_update"
        self._attr_entity_description = "Automatically update display when text or settings change"
        self._is_on = False  # Default to manual updates only

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
        if last_state is not None:
            self._is_on = last_state.state == "on"
            _LOGGER.debug("Restored auto-update state: %s", self._is_on)

    @property
    def is_on(self) -> bool:
        """Return True if auto-update is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-update."""
        self._is_on = True
        _LOGGER.debug("Auto-update enabled - display will update automatically on changes")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-update."""
        self._is_on = False
        _LOGGER.debug("Auto-update disabled - use update button for manual updates")


class iPIXELClock24HSwitch(SwitchEntity, RestoreEntity):
    """Representation of an iPIXEL Color clock 24h format setting."""

    _attr_icon = "mdi:clock-time-four-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the clock 24h switch."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Clock 24h"
        self._attr_unique_id = f"{address}_clock_24h"
        self._attr_entity_description = "Use 24-hour format for clock display"
        self._is_on = True  # Default to 24h format

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
        if last_state is not None:
            self._is_on = last_state.state == "on"
            _LOGGER.debug("Restored clock 24h state: %s", self._is_on)

    @property
    def is_on(self) -> bool:
        """Return True if 24h format is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable 24h format."""
        self._is_on = True
        _LOGGER.debug("Clock 24h format enabled")
        await self._trigger_auto_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable 24h format (use 12h)."""
        self._is_on = False
        _LOGGER.debug("Clock 12h format enabled")
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled and in clock mode."""
        try:
            # Check if we're in clock mode
            mode_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "mode_select", "select")
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None

            if mode_state and mode_state.state == "clock":
                # Check auto-update setting
                auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
                auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None

                if auto_update_state and auto_update_state.state == "on":
                    await update_ipixel_display(self.hass, self._name, self._api)
                    _LOGGER.debug("Auto-update triggered due to clock 24h change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)


class iPIXELClockShowDateSwitch(SwitchEntity, RestoreEntity):
    """Representation of an iPIXEL Color clock show date setting."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the clock show date switch."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Clock Show Date"
        self._attr_unique_id = f"{address}_clock_show_date"
        self._attr_entity_description = "Show date alongside time in clock display"
        self._is_on = True  # Default to showing date

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
        if last_state is not None:
            self._is_on = last_state.state == "on"
            _LOGGER.debug("Restored clock show date state: %s", self._is_on)

    @property
    def is_on(self) -> bool:
        """Return True if show date is enabled."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable showing date."""
        self._is_on = True
        _LOGGER.debug("Clock show date enabled")
        await self._trigger_auto_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable showing date."""
        self._is_on = False
        _LOGGER.debug("Clock show date disabled")
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled and in clock mode."""
        try:
            # Check if we're in clock mode
            mode_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "mode_select", "select")
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None

            if mode_state and mode_state.state == "clock":
                # Check auto-update setting
                auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
                auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None

                if auto_update_state and auto_update_state.state == "on":
                    await update_ipixel_display(self.hass, self._name, self._api)
                    _LOGGER.debug("Auto-update triggered due to clock show date change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)
