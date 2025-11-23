"""Common utilities for iPIXEL Color integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

_LOGGER = logging.getLogger(__name__)


async def resolve_template_variables(hass: HomeAssistant, text: str) -> str:
    """Resolve Home Assistant template variables in text.
    
    Supports all Jinja2 patterns:
        {{ states('sensor.temperature') }}
        {% if condition %}text{% endif %}
        {# comments #}
    
    Args:
        hass: Home Assistant instance
        text: Text containing template variables
        
    Returns:
        Text with variables resolved
    """
    if not text or not any(pattern in text for pattern in ['{%', '{{', '{#']):
        return text
    
    try:
        template = Template(text, hass)
        result = template.async_render()
        return str(result)
    except Exception as e:
        _LOGGER.warning("Template error in '%s': %s", text, e)
        return text


async def update_ipixel_display(hass: HomeAssistant, device_name: str, api, text: str = None) -> bool:
    """Update iPIXEL display with current settings - can be called from anywhere.
    
    Args:
        hass: Home Assistant instance
        device_name: Device name for entity ID lookups
        api: iPIXEL API instance
        text: Text to display, or None to get from text entity
        
    Returns:
        True if update was successful
    """
    try:
        # Get current text if not provided
        if text is None:
            text_entity_id = f"text.{device_name.lower().replace(' ', '_')}_display"
            text_state = hass.states.get(text_entity_id)
            if not text_state or text_state.state in ("unknown", "unavailable", ""):
                _LOGGER.warning("No text to display - skipping update")
                return False
            text = text_state.state
        
        # Get style settings from the unified style control entity
        style_entity_id = f"ipixel_color.{device_name.lower().replace(' ', '_')}_style"
        style_state = hass.states.get(style_entity_id)
        
        if style_state and style_state.attributes:
            # Get settings from style control entity attributes
            font_name = style_state.attributes.get("font", "OpenSans-Light.ttf")
            font_size = style_state.attributes.get("font_size", 0.0)
            antialias = style_state.attributes.get("antialias", True)
            line_spacing = style_state.attributes.get("line_spacing", 0)
        else:
            # Fallback to legacy sensor style entity
            sensor_style_entity_id = f"sensor.{device_name.lower().replace(' ', '_')}_style"
            sensor_style_state = hass.states.get(sensor_style_entity_id)
            
            if sensor_style_state and sensor_style_state.attributes:
                font_name = sensor_style_state.attributes.get("font", "OpenSans-Light.ttf")
                font_size = sensor_style_state.attributes.get("font_size", 0.0)
                antialias = sensor_style_state.attributes.get("antialias", True)
                line_spacing = sensor_style_state.attributes.get("line_spacing", 0)
            else:
                # Fallback to defaults if no style entity available
                font_name = "OpenSans-Light.ttf"
                font_size = None
                antialias = True
                line_spacing = 0
                _LOGGER.warning("Style entity not found, using default settings")
        
        # Connect if needed
        if not api.is_connected:
            _LOGGER.debug("Reconnecting to device for display update")
            await api.connect()
        
        # Resolve templates and process escape sequences
        template_resolved = await resolve_template_variables(hass, text)
        processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')
        
        # Send text to display with current settings
        success = await api.display_text(processed_text, antialias, font_size, font_name, line_spacing)
        
        if success:
            _LOGGER.info("Display update successful: %s (font: %s, size: %s, antialias: %s, spacing: %spx)", 
                       processed_text, font_name or "OpenSans-Light.ttf", 
                       f"{font_size:.1f}px" if font_size else "Auto", antialias, line_spacing)
        else:
            _LOGGER.error("Display update failed")
            
        return success
        
    except Exception as err:
        _LOGGER.error("Error during display update: %s", err)
        return False


async def _get_entity_setting(hass: HomeAssistant, device_name: str, platform: str, setting: str, value_type=str):
    """Get setting from Home Assistant entity.
    
    Args:
        hass: Home Assistant instance
        device_name: Device name for entity ID
        platform: Platform type (select, number, switch)
        setting: Setting name (font, font_size, etc.)
        value_type: Type to convert value to
        
    Returns:
        Entity value or appropriate default
    """
    try:
        entity_id = f"{platform}.{device_name.lower().replace(' ', '_')}_{setting}"
        state = hass.states.get(entity_id)
        
        if not state or state.state in ("unknown", "unavailable", ""):
            return _get_default_value(setting, value_type)
        
        if value_type == bool:
            return state.state == "on"
        elif value_type == float:
            value = float(state.state)
            # Return None for 0 font size (auto-sizing)
            return None if setting == "font_size" and value == 0 else value
        elif value_type == int:
            return int(float(state.state))
        else:
            # String value - return the font filename directly
            return state.state
            
    except Exception as err:
        _LOGGER.debug("Could not get %s setting: %s", setting, err)
        return _get_default_value(setting, value_type)


def _get_default_value(setting: str, value_type):
    """Get default value for a setting."""
    defaults = {
        "font": "OpenSans-Light.ttf",
        "font_size": None,
        "line_spacing": 0,
        "antialiasing": True
    }
    default = defaults.get(setting)
    
    if value_type == bool and default is None:
        return True
    elif value_type in (int, float) and default is None:
        return 0 if setting == "line_spacing" else None
    
    return default