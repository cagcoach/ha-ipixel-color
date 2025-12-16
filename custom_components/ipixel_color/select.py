"""Select entity for iPIXEL Color font selection."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import Event, EventStateChangedData

from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME, AVAILABLE_MODES, DEFAULT_MODE, MODE_TIMER
from .common import get_entity_id_by_unique_id
from .common import update_ipixel_display
from .fonts import get_available_fonts

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color select entities."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        iPIXELFontSelect(hass, api, entry, address, name),
        iPIXELModeSelect(hass, api, entry, address, name),
        iPIXELClockStyleSelect(hass, api, entry, address, name),
        iPIXELTimerEntitySelect(hass, api, entry, address, name),
    ])


class iPIXELFontSelect(SelectEntity, RestoreEntity):
    """Representation of an iPIXEL Color font selection."""

    def __init__(
        self, 
        hass: HomeAssistant,
        api: iPIXELAPI, 
        entry: ConfigEntry, 
        address: str, 
        name: str
    ) -> None:
        """Initialize the font select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Font"
        self._attr_unique_id = f"{address}_font_select"
        self._attr_entity_description = "Select font for text display"

        # Get available fonts from all locations
        self._attr_options = get_available_fonts()
        self._attr_current_option = "OpenSans-Light.ttf" if "OpenSans-Light.ttf" in self._attr_options else self._attr_options[0]
        
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
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored font selection: %s", self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected font."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a font option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.debug("Font changed to: %s", option)
            
            # Trigger display update if auto-update is enabled
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid font option: %s", option)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None
            
            if auto_update_state and auto_update_state.state == "on":
                # Use common update function directly
                await update_ipixel_display(self.hass, self._name, self._api)
                _LOGGER.debug("Auto-update triggered display refresh due to font change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class iPIXELModeSelect(SelectEntity, RestoreEntity):
    """Representation of an iPIXEL Color mode selection."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the mode select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Mode"
        self._attr_unique_id = f"{address}_mode_select"
        self._attr_entity_description = "Select display mode (textimage, clock, rhythm, fun)"

        # Set available mode options
        self._attr_options = AVAILABLE_MODES
        self._attr_current_option = DEFAULT_MODE

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
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored mode selection: %s", self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a mode option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.info("Mode changed to: %s", option)

            # Trigger display update if auto-update is enabled
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid mode option: %s", option)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None

            if auto_update_state and auto_update_state.state == "on":
                # Use common update function directly
                await update_ipixel_display(self.hass, self._name, self._api)
                _LOGGER.debug("Auto-update triggered display refresh due to mode change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class iPIXELClockStyleSelect(SelectEntity, RestoreEntity):
    """Representation of an iPIXEL Color clock style selection."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the clock style select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Clock Style"
        self._attr_unique_id = f"{address}_clock_style_select"
        self._attr_entity_description = "Select clock display style (0-8)"

        # Clock styles 0-8
        self._attr_options = ["0", "1", "2", "3", "4", "5", "6", "7", "8"]
        self._attr_current_option = "1"  # Default style

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
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored clock style selection: %s", self._attr_current_option)

    @property
    def current_option(self) -> str | None:
        """Return the current selected clock style."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a clock style option."""
        if option in self._attr_options:
            self._attr_current_option = option
            _LOGGER.info("Clock style changed to: %s", option)

            # Trigger display update if auto-update is enabled and in clock mode
            await self._trigger_auto_update()
        else:
            _LOGGER.error("Invalid clock style option: %s", option)

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
                    # Use common update function directly
                    await update_ipixel_display(self.hass, self._name, self._api)
                    _LOGGER.debug("Auto-update triggered display refresh due to clock style change")
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True


class iPIXELTimerEntitySelect(SelectEntity, RestoreEntity):
    """Select entity to link a Home Assistant timer to the iPIXEL display."""

    _attr_icon = "mdi:timer-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the timer entity select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Timer Entity"
        self._attr_unique_id = f"{address}_timer_entity_select"
        self._attr_entity_description = "Select a Home Assistant timer entity to display countdown"
        self._unsub_state_change = None

        # Will be populated with timer entities
        self._attr_options = ["none"]
        self._attr_current_option = "none"

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

        # Update available timer entities
        self._update_timer_options()

        # Restore last state if available
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
            _LOGGER.debug("Restored timer entity selection: %s", self._attr_current_option)
            # Set up listener for the restored timer
            if self._attr_current_option != "none":
                self._setup_timer_listener(self._attr_current_option)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._unsub_state_change:
            self._unsub_state_change()
            self._unsub_state_change = None

    def _update_timer_options(self) -> None:
        """Update the list of available timer entities."""
        timer_entities = ["none"]
        for entity_id in self.hass.states.async_entity_ids("timer"):
            timer_entities.append(entity_id)
        self._attr_options = timer_entities
        _LOGGER.debug("Available timer entities: %s", timer_entities)

    @property
    def current_option(self) -> str | None:
        """Return the current selected timer entity."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select a timer entity option."""
        # Refresh available timers first
        self._update_timer_options()

        if option not in self._attr_options:
            _LOGGER.error("Invalid timer entity option: %s", option)
            return

        # Remove old listener
        if self._unsub_state_change:
            self._unsub_state_change()
            self._unsub_state_change = None

        self._attr_current_option = option
        _LOGGER.info("Timer entity changed to: %s", option)

        # Set up new listener if a timer is selected
        if option != "none":
            self._setup_timer_listener(option)

    def _setup_timer_listener(self, timer_entity_id: str) -> None:
        """Set up state change listener for the timer entity."""
        @callback
        def async_timer_state_changed(event: Event[EventStateChangedData]) -> None:
            """Handle timer state changes."""
            new_state = event.data["new_state"]
            old_state = event.data["old_state"]

            if new_state is None:
                return

            _LOGGER.debug(
                "Timer %s changed: %s -> %s",
                timer_entity_id,
                old_state.state if old_state else "None",
                new_state.state
            )

            # Only trigger when timer becomes active (started)
            if new_state.state == "active":
                # Check if we're in timer mode
                mode_entity_id = get_entity_id_by_unique_id(
                    self.hass, self._address, "mode_select", "select"
                )
                mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None

                if mode_state and mode_state.state == MODE_TIMER:
                    # Get the remaining duration from the timer
                    duration = new_state.attributes.get("duration", "0:00:00")
                    # Parse duration string (H:MM:SS or M:SS format)
                    duration_seconds = self._parse_duration(duration)

                    if duration_seconds > 0:
                        _LOGGER.info(
                            "Timer started! Displaying %d second countdown",
                            duration_seconds
                        )
                        # Schedule the timer GIF display
                        self.hass.async_create_task(
                            self._display_timer(duration_seconds)
                        )

        self._unsub_state_change = async_track_state_change_event(
            self.hass, timer_entity_id, async_timer_state_changed
        )
        _LOGGER.debug("Set up state listener for timer: %s", timer_entity_id)

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds.

        Accepts formats: H:MM:SS, MM:SS, or seconds as string
        """
        try:
            parts = duration_str.split(":")
            if len(parts) == 3:
                # H:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                # MM:SS or M:SS
                return int(parts[0]) * 60 + int(parts[1])
            else:
                # Just seconds
                return int(float(duration_str))
        except (ValueError, IndexError) as err:
            _LOGGER.error("Failed to parse duration '%s': %s", duration_str, err)
            return 0

    async def _display_timer(self, duration_seconds: int) -> None:
        """Display the timer countdown GIF on the device."""
        try:
            # Get colors from light entities
            from .common import get_color_from_light_entity

            text_color_hex = get_color_from_light_entity(
                self.hass, self._address, "text_color", default="00ff00"
            )
            bg_color_hex = get_color_from_light_entity(
                self.hass, self._address, "background_color", default="000000"
            )

            # Convert hex to RGB tuples
            text_color = (
                int(text_color_hex[0:2], 16),
                int(text_color_hex[2:4], 16),
                int(text_color_hex[4:6], 16),
            )
            bg_color = (
                int(bg_color_hex[0:2], 16),
                int(bg_color_hex[2:4], 16),
                int(bg_color_hex[4:6], 16),
            )

            # Connect if needed
            if not self._api.is_connected:
                _LOGGER.debug("Reconnecting to device for timer display")
                await self._api.connect()

            # Display the timer GIF
            success = await self._api.display_timer_gif(
                duration_seconds=duration_seconds,
                text_color=text_color,
                bg_color=bg_color,
            )

            if success:
                _LOGGER.info("Timer countdown displayed successfully")
            else:
                _LOGGER.error("Failed to display timer countdown")

        except Exception as err:
            _LOGGER.error("Error displaying timer: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True