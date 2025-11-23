"""Custom style control entity for iPIXEL Color with full UI support."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import update_ipixel_display

_LOGGER = logging.getLogger(__name__)

SUPPORT_STYLE_FONT = 1
SUPPORT_STYLE_SIZE = 2
SUPPORT_STYLE_ANTIALIAS = 4
SUPPORT_STYLE_SPACING = 8
SUPPORT_STYLE_PRESET = 16

SUPPORT_STYLE = (
    SUPPORT_STYLE_FONT
    | SUPPORT_STYLE_SIZE
    | SUPPORT_STYLE_ANTIALIAS
    | SUPPORT_STYLE_SPACING
    | SUPPORT_STYLE_PRESET
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color style control entity."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    api = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([iPIXELStyleControl(hass, api, entry, address, name)])


class iPIXELStyleControl(RestoreEntity):
    """Custom entity for comprehensive style control with UI support."""
    
    _attr_should_poll = False
    _attr_supported_features = SUPPORT_STYLE

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the style control entity."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._device_name = name
        self._attr_name = f"{name} Style"
        self._attr_unique_id = f"{address}_style_control"
        self._attr_icon = "mdi:palette-outline"
        
        # Style state
        self._is_on = True  # Style control is always "on" when configured
        self._font = "OpenSans-Light.ttf"
        self._font_size = 0.0  # Auto-size
        self._antialias = True
        self._line_spacing = 0
        self._current_preset = "default"
        
        # Available options
        self._available_presets = ["default", "large", "pixel", "smooth", "compact"]
        self._preset_definitions = {
            "default": {"font": "OpenSans-Light.ttf", "font_size": 0, "antialias": True, "line_spacing": 0},
            "large": {"font": "7x5.ttf", "font_size": 8, "antialias": False, "line_spacing": 2},
            "pixel": {"font": "5x5.ttf", "font_size": 10, "antialias": False, "line_spacing": 1},
            "smooth": {"font": "OpenSans-Light.ttf", "font_size": 12.5, "antialias": True, "line_spacing": 3},
            "compact": {"font": "3x5-de.ttf", "font_size": 6, "antialias": False, "line_spacing": 0}
        }
        
        # Device info
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
            if last_state.attributes:
                self._font = last_state.attributes.get("font", self._font)
                self._font_size = float(last_state.attributes.get("font_size", self._font_size))
                self._antialias = last_state.attributes.get("antialias", self._antialias)
                self._line_spacing = int(last_state.attributes.get("line_spacing", self._line_spacing))
                self._current_preset = last_state.attributes.get("current_preset", self._current_preset)
                _LOGGER.debug("Restored style state from previous session")

    @property
    def state(self) -> str:
        """Return the state of the style control."""
        return "on" if self._is_on else "off"

    @property
    def is_on(self) -> bool:
        """Return true if style control is on."""
        return self._is_on

    @property
    def supported_features(self) -> int:
        """Return supported features."""
        return self._attr_supported_features

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes with current style settings."""
        # Get available fonts dynamically
        fonts_dir = Path(__file__).parent / "fonts"
        available_fonts = ["OpenSans-Light.ttf"]
        if fonts_dir.exists():
            for font_file in fonts_dir.glob("*.ttf"):
                if font_file.name not in available_fonts:
                    available_fonts.append(font_file.name)
            for font_file in fonts_dir.glob("*.otf"):
                available_fonts.append(font_file.name)

        return {
            # Current style settings
            "font": self._font,
            "font_size": self._font_size,
            "font_size_display": "auto" if self._font_size == 0 else f"{self._font_size:.1f}",
            "antialias": self._antialias,
            "line_spacing": self._line_spacing,
            "current_preset": self._current_preset,
            
            # Available options for UI
            "available_fonts": sorted(available_fonts),
            "available_presets": self._available_presets,
            "preset_definitions": self._preset_definitions,
            
            # UI support flags
            "supported_features": self._attr_supported_features,
            "font_size_min": 0,
            "font_size_max": 64,
            "line_spacing_min": 0,
            "line_spacing_max": 20,
            
            # Current style as JSON for easy copying
            "style_json": json.dumps({
                "font": self._font,
                "font_size": self._font_size,
                "antialias": self._antialias,
                "line_spacing": self._line_spacing
            }),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on/activate style control (mostly for completeness)."""
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off style control (disable style changes)."""
        self._is_on = False
        self.async_write_ha_state()

    async def async_set_style(
        self,
        font: Optional[str] = None,
        font_size: Optional[float] = None,
        antialias: Optional[bool] = None,
        line_spacing: Optional[int] = None,
        preset: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Set style parameters directly (like light.turn_on with brightness, color, etc)."""
        try:
            # If preset is specified, apply it first
            if preset and preset in self._preset_definitions:
                preset_style = self._preset_definitions[preset]
                self._font = preset_style["font"]
                self._font_size = float(preset_style["font_size"])
                self._antialias = preset_style["antialias"]
                self._line_spacing = preset_style["line_spacing"]
                self._current_preset = preset
                _LOGGER.info(f"Applied style preset: {preset}")
            else:
                # Apply individual parameters
                if font is not None:
                    self._font = font
                if font_size is not None:
                    self._font_size = float(font_size)
                if antialias is not None:
                    self._antialias = bool(antialias)
                if line_spacing is not None:
                    self._line_spacing = int(line_spacing)
                
                # Clear preset since we're using custom settings
                if any(param is not None for param in [font, font_size, antialias, line_spacing]):
                    self._current_preset = "custom"
                    _LOGGER.info("Applied custom style settings")

            # Activate the style control if it was off
            self._is_on = True
            
            # Update the entity state
            self.async_write_ha_state()

            # Trigger auto-update if enabled
            await self._trigger_auto_update()

        except Exception as err:
            _LOGGER.error("Error setting style: %s", err)

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = f"switch.{self._device_name.lower().replace(' ', '_')}_auto_update"
            auto_update_state = self.hass.states.get(auto_update_entity_id)
            
            if auto_update_state and auto_update_state.state == "on":
                # Update display with new style
                success = await update_ipixel_display(self.hass, self._device_name, self._api)
                if success:
                    _LOGGER.debug("Auto-update triggered display refresh with new style")
                else:
                    _LOGGER.error("Failed to update display with new style")
                        
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    # Properties to make it behave like a light entity for UI purposes
    @property
    def font(self) -> str:
        """Return current font."""
        return self._font

    @property
    def font_size(self) -> float:
        """Return current font size."""
        return self._font_size

    @property
    def antialias(self) -> bool:
        """Return current antialiasing setting."""
        return self._antialias

    @property
    def line_spacing(self) -> int:
        """Return current line spacing."""
        return self._line_spacing

    @property
    def current_preset(self) -> str:
        """Return current preset name."""
        return self._current_preset

    def get_style_dict(self) -> Dict[str, Any]:
        """Get current style as a dictionary for other entities to use."""
        return {
            "font": self._font,
            "font_size": self._font_size,
            "antialias": self._antialias,
            "line_spacing": self._line_spacing,
            "current_preset": self._current_preset
        }