"""Select entity for iPIXEL Color font selection."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .api import iPIXELAPI
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import async_get as async_get_restore_data

from .const import (
    DOMAIN,
    CONF_ADDRESS,
    CONF_NAME,
    AVAILABLE_MODES,
    DEFAULT_MODE,
    DEFAULT_TEXT_ANIMATION,
    TEXT_ANIMATION_OPTIONS,
    text_animation_option,
)
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
        iPIXELTextAnimationSelect(hass, api, entry, address, name),
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


class iPIXELTextAnimationSelect(SelectEntity, RestoreEntity):
    """Text-mode animation, shown as "<number> <name>" (e.g. "1 Scroll left").

    Replaces the earlier 0-7 Text Animation number entity; its last value is
    carried over the first time this select is added.
    """

    _attr_icon = "mdi:animation"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the text animation select."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = "Text Animation"
        self._attr_unique_id = f"{address}_text_animation_select"
        self._attr_options = TEXT_ANIMATION_OPTIONS
        self._attr_current_option = DEFAULT_TEXT_ANIMATION

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=name,
            manufacturer="iPIXEL",
            model="LED Matrix Display",
            sw_version="1.0",
        )

    async def async_added_to_hass(self) -> None:
        """Restore the last animation, or migrate it from the old number entity."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in self._attr_options:
            self._attr_current_option = last_state.state
        else:
            migrated = self._migrate_from_number()
            if migrated is not None:
                self._attr_current_option = migrated
        self._remove_old_number()

    def _old_number_entity_id(self) -> str | None:
        registry = er.async_get(self.hass)
        return registry.async_get_entity_id(
            "number", DOMAIN, f"{self._address}_text_animation"
        )

    def _migrate_from_number(self) -> str | None:
        """Return the old number entity's last value as a select option."""
        entity_id = self._old_number_entity_id()
        if entity_id is None:
            return None
        try:
            stored = async_get_restore_data(self.hass).last_states.get(entity_id)
            if stored is None:
                return None
            option = text_animation_option(int(float(stored.state.state)))
        except (AttributeError, TypeError, ValueError):
            return None
        _LOGGER.info("Migrated text animation %s from %s", option, entity_id)
        return option

    def _remove_old_number(self) -> None:
        """Remove the replaced number entity so it does not linger as unavailable."""
        entity_id = self._old_number_entity_id()
        if entity_id is not None:
            er.async_get(self.hass).async_remove(entity_id)
            _LOGGER.info("Removed %s, replaced by the Text Animation select", entity_id)

    @property
    def current_option(self) -> str | None:
        """Return the current animation."""
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Select an animation."""
        if option not in self._attr_options:
            _LOGGER.error("Invalid text animation option: %s", option)
            return
        self._attr_current_option = option
        self.async_write_ha_state()
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Refresh the display if auto-update is on and the panel is in text mode."""
        try:
            mode_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "mode_select", "select")
            mode_state = self.hass.states.get(mode_entity_id) if mode_entity_id else None
            if not mode_state or mode_state.state != "text":
                return
            auto_update_entity_id = get_entity_id_by_unique_id(self.hass, self._address, "auto_update", "switch")
            auto_update_state = self.hass.states.get(auto_update_entity_id) if auto_update_entity_id else None
            if auto_update_state and auto_update_state.state == "on":
                await update_ipixel_display(self.hass, self._name, self._api)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True
