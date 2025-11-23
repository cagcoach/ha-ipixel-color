"""Custom style entity for iPIXEL Color combining multiple text settings."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.core import ServiceCall
from pathlib import Path

from .api import iPIXELAPI
from .const import DOMAIN, CONF_ADDRESS, CONF_NAME
from .common import update_ipixel_display

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iPIXEL Color style entity."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    api = hass.data[DOMAIN][entry.entry_id]
    
    style_entity = iPIXELStyleEntity(hass, api, entry, address, name)
    async_add_entities([style_entity])
    
    # Register services for style control
    async def handle_apply_style(call: ServiceCall) -> None:
        """Handle apply style service call."""
        entity_id = call.data.get("entity_id")
        style_data = call.data.get("style", {})
        
        for entity in hass.data["sensor"].entities:
            if entity.entity_id == entity_id and isinstance(entity, iPIXELStyleEntity):
                await entity.async_apply_style(style_data)
    
    async def handle_apply_preset(call: ServiceCall) -> None:
        """Handle apply preset service call."""
        entity_id = call.data.get("entity_id")
        preset_name = call.data.get("preset")
        
        for entity in hass.data["sensor"].entities:
            if entity.entity_id == entity_id and isinstance(entity, iPIXELStyleEntity):
                await entity.async_apply_preset(preset_name)
    
    hass.services.async_register(
        DOMAIN,
        "apply_style",
        handle_apply_style,
        schema={
            "entity_id": str,
            "style": dict,
        }
    )
    
    hass.services.async_register(
        DOMAIN,
        "apply_style_preset",
        handle_apply_preset,
        schema={
            "entity_id": str,
            "preset": str,
        }
    )


class iPIXELStyleEntity(SensorEntity, RestoreEntity):
    """Custom entity combining all text style settings."""
    
    _attr_icon = "mdi:palette-outline"

    def __init__(
        self,
        hass: HomeAssistant,
        api: iPIXELAPI,
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the style entity."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = f"{name} Style"
        self._attr_unique_id = f"{address}_style"
        
        # Style attributes
        self._font = "OpenSans-Light.ttf"
        self._font_size = 0.0  # 0 = auto
        self._antialias = True
        self._line_spacing = 0
        
        # Style presets with optimized font sizes for pixel fonts
        self._presets = {
            "default": {
                "font": "OpenSans-Light.ttf",
                "font_size": 0,  # Auto-sizing
                "antialias": True,
                "line_spacing": 0
            },
            "large": {
                "font": "7x5.ttf", 
                "font_size": 8,  # Optimal for 7x5 font
                "antialias": False,
                "line_spacing": 2
            },
            "pixel": {
                "font": "5x5.ttf",
                "font_size": 10,  # Optimal for 5x5 font
                "antialias": False,
                "line_spacing": 1
            },
            "smooth": {
                "font": "OpenSans-Light.ttf",
                "font_size": 12.5,
                "antialias": True,
                "line_spacing": 3
            },
            "compact": {
                "font": "3x5-de.ttf",
                "font_size": 6,  # Optimal for 3x5 font
                "antialias": False,
                "line_spacing": 0
            }
        }
        
        self._current_preset = "default"
        
        # Device info for grouping
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
            # Restore from attributes if available
            if last_state.attributes:
                self._font = last_state.attributes.get("font", self._font)
                self._font_size = float(last_state.attributes.get("font_size", self._font_size))
                self._antialias = last_state.attributes.get("antialias", self._antialias)
                self._line_spacing = int(last_state.attributes.get("line_spacing", self._line_spacing))
                self._current_preset = last_state.attributes.get("current_preset", self._current_preset)
                _LOGGER.debug("Restored style settings from state")
    
    @property
    def native_value(self) -> str:
        """Return current style as a readable string."""
        if self._font_size == 0:
            size_str = "auto"
        else:
            size_str = f"{self._font_size:.1f}px" if self._font_size % 1 else f"{int(self._font_size)}px"
        
        return f"{self._current_preset}: {self._font} {size_str}"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all style settings as attributes."""
        # Get available fonts dynamically
        fonts_dir = Path(__file__).parent / "fonts"
        available_fonts = ["OpenSans-Light.ttf"]  # Default
        if fonts_dir.exists():
            for font_file in fonts_dir.glob("*.ttf"):
                if font_file.name not in available_fonts:
                    available_fonts.append(font_file.name)
            for font_file in fonts_dir.glob("*.otf"):
                available_fonts.append(font_file.name)
        
        return {
            "font": self._font,
            "font_size": self._font_size,
            "font_size_display": "auto" if self._font_size == 0 else f"{self._font_size:.1f}",
            "antialias": self._antialias,
            "line_spacing": self._line_spacing,
            "current_preset": self._current_preset,
            "available_presets": list(self._presets.keys()),
            "available_fonts": sorted(available_fonts),
            "editable": True,
            "style_json": json.dumps({
                "font": self._font,
                "font_size": self._font_size,
                "antialias": self._antialias,
                "line_spacing": self._line_spacing
            })
        }
    
    async def async_apply_style(self, style: dict[str, Any]) -> None:
        """Apply a custom style configuration.
        
        Args:
            style: Dictionary with style settings
                - font: Font filename
                - font_size: Font size (0 for auto)
                - antialias: Boolean for smooth rendering
                - line_spacing: Pixel spacing between lines
        """
        try:
            # Update style settings
            if "font" in style:
                self._font = str(style["font"])
            if "font_size" in style:
                self._font_size = float(style["font_size"])
            if "antialias" in style:
                self._antialias = bool(style["antialias"])
            if "line_spacing" in style:
                self._line_spacing = int(style["line_spacing"])
            
            # Clear preset since this is a custom style
            self._current_preset = "custom"
            
            # Update entity state
            self.async_write_ha_state()
            
            # Check if auto-update is enabled and trigger display update
            await self._trigger_auto_update()
            
            _LOGGER.info("Applied custom style: %s", style)
            
        except (ValueError, TypeError, KeyError) as err:
            _LOGGER.error("Invalid style configuration: %s", err)
    
    async def async_apply_preset(self, preset_name: str) -> None:
        """Apply a predefined style preset.
        
        Args:
            preset_name: Name of the preset to apply
        """
        if preset_name not in self._presets:
            _LOGGER.error("Unknown preset: %s. Available: %s", 
                         preset_name, list(self._presets.keys()))
            return
        
        preset = self._presets[preset_name]
        self._font = preset["font"]
        self._font_size = float(preset["font_size"])
        self._antialias = preset["antialias"]
        self._line_spacing = preset["line_spacing"]
        self._current_preset = preset_name
        
        # Update entity state
        self.async_write_ha_state()
        
        # Check if auto-update is enabled and trigger display update
        await self._trigger_auto_update()
        
        _LOGGER.info("Applied preset style: %s", preset_name)
    
    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled."""
        try:
            # Check auto-update setting
            auto_update_entity_id = f"switch.{self._name.lower().replace(' ', '_')}_auto_update"
            auto_update_state = self.hass.states.get(auto_update_entity_id)
            
            if auto_update_state and auto_update_state.state == "on":
                # Get current text
                text_entity_id = f"text.{self._name.lower().replace(' ', '_')}_display"
                text_state = self.hass.states.get(text_entity_id)
                
                if text_state and text_state.state:
                    # Update display with new style
                    from .common import resolve_template_variables
                    
                    template_resolved = await resolve_template_variables(self.hass, text_state.state)
                    processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')
                    
                    success = await self._api.display_text(
                        processed_text, 
                        self._antialias, 
                        self._font_size if self._font_size != 0 else None,
                        self._font,
                        self._line_spacing
                    )
                    
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
    
    def get_style_dict(self) -> dict[str, Any]:
        """Get current style as a dictionary for other entities to use."""
        return {
            "font": self._font,
            "font_size": self._font_size,
            "antialias": self._antialias,
            "line_spacing": self._line_spacing
        }