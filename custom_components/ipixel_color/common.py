"""Common utilities for iPIXEL Color integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from .const import MODE_TEXT_IMAGE, MODE_TEXT, MODE_CLOCK

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
        # Get current mode
        mode = await _get_entity_setting(hass, device_name, "select", "mode", str)
        if not mode:
            mode = MODE_TEXT_IMAGE  # Default to textimage mode

        _LOGGER.debug("Updating display in mode: %s", mode)

        # Route to appropriate mode handler
        if mode == MODE_TEXT_IMAGE:
            return await _update_textimage_mode(hass, device_name, api, text)
        elif mode == MODE_TEXT:
            return await _update_text_mode(hass, device_name, api, text)
        elif mode == MODE_CLOCK:
            return await _update_clock_mode(hass, device_name, api)
        else:
            _LOGGER.warning("Unknown mode: %s, falling back to textimage", mode)
            return await _update_textimage_mode(hass, device_name, api, text)

    except Exception as err:
        _LOGGER.error("Error during display update: %s", err)
        return False


async def _update_textimage_mode(hass: HomeAssistant, device_name: str, api, text: str = None) -> bool:
    """Update display in text/image mode.

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
        
        # Get all current settings
        font_name = await _get_entity_setting(hass, device_name, "select", "font")
        font_size = await _get_entity_setting(hass, device_name, "number", "font_size", float)
        line_spacing = await _get_entity_setting(hass, device_name, "number", "line_spacing", int)
        antialias = await _get_entity_setting(hass, device_name, "switch", "antialiasing", bool)

        # Get color settings
        text_color = await _get_entity_setting(hass, device_name, "text", "text_color")
        if not text_color:
            text_color = "ffffff"  # Default to white

        bg_color = await _get_entity_setting(hass, device_name, "text", "background_color")
        if not bg_color:
            bg_color = "000000"  # Default to black

        # Connect if needed
        if not api.is_connected:
            _LOGGER.debug("Reconnecting to device for display update")
            await api.connect()

        # Resolve templates and process escape sequences
        template_resolved = await resolve_template_variables(hass, text)
        processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')

        # Send text to display with current settings
        success = await api.display_text(processed_text, antialias, font_size, font_name, line_spacing, text_color, bg_color)
        
        if success:
            _LOGGER.info("Display update successful: %s (font: %s, size: %s, antialias: %s, spacing: %spx, text: #%s, bg: #%s)",
                       processed_text, font_name or "OpenSans-Light.ttf",
                       f"{font_size:.1f}px" if font_size else "Auto", antialias, line_spacing, text_color, bg_color)
        else:
            _LOGGER.error("Display update failed")
            
        return success
        
    except Exception as err:
        _LOGGER.error("Error in textimage mode update: %s", err)
        return False


async def _update_clock_mode(hass: HomeAssistant, device_name: str, api) -> bool:
    """Update display in clock mode.

    Args:
        hass: Home Assistant instance
        device_name: Device name for entity ID lookups
        api: iPIXEL API instance

    Returns:
        True if update was successful
    """
    try:
        # Get clock settings from entities
        clock_style = await _get_entity_setting(hass, device_name, "select", "clock_style", int)
        if clock_style is None:
            clock_style = 1  # Default style

        format_24 = await _get_entity_setting(hass, device_name, "switch", "clock_24h", bool)
        if format_24 is None:
            format_24 = True  # Default to 24h

        show_date = await _get_entity_setting(hass, device_name, "switch", "clock_show_date", bool)
        if show_date is None:
            show_date = True  # Default to showing date

        # Connect if needed
        if not api.is_connected:
            _LOGGER.debug("Reconnecting to device for clock mode update")
            await api.connect()

        # Send clock mode command
        success = await api.set_clock_mode(
            style=clock_style,
            date="",  # Use current date
            show_date=show_date,
            format_24=format_24
        )

        if success:
            _LOGGER.info("Clock mode activated: style=%d, 24h=%s, show_date=%s",
                       clock_style, format_24, show_date)
        else:
            _LOGGER.error("Failed to activate clock mode")

        return success

    except Exception as err:
        _LOGGER.error("Error in clock mode update: %s", err)
        return False


async def _update_text_mode(hass: HomeAssistant, device_name: str, api, text: str = None) -> bool:
    """Update display in text mode using pypixelcolor.

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

        # Get pypixelcolor text settings (reusing existing entities where possible)

        # Reuse existing font selector - convert TTF filename to full path
        font_name = await _get_entity_setting(hass, device_name, "select", "font")
        if font_name and font_name.endswith(('.ttf', '.otf')):
            # Custom TTF/OTF font from fonts/ folder
            from pathlib import Path
            font_path = Path(__file__).parent / "fonts" / font_name
            font = str(font_path) if font_path.exists() else "CUSONG"
        else:
            # Use pypixelcolor's built-in fonts or default
            font = "CUSONG"

        # Color - need new text entity for hex color input
        color = await _get_entity_setting(hass, device_name, "text", "text_color")
        if not color:
            color = "ffffff"  # Default to white

        # Animation - need new number entity
        animation = await _get_entity_setting(hass, device_name, "number", "text_animation", int)
        if animation is None:
            animation = 0  # Default to no animation

        # Speed - need new number entity
        speed = await _get_entity_setting(hass, device_name, "number", "text_speed", int)
        if speed is None:
            speed = 80  # Default speed

        # Rainbow mode - need new number entity
        rainbow_mode = await _get_entity_setting(hass, device_name, "number", "text_rainbow", int)
        if rainbow_mode is None:
            rainbow_mode = 0  # Default to no rainbow

        # Connect if needed
        if not api.is_connected:
            _LOGGER.debug("Reconnecting to device for text mode update")
            await api.connect()

        # Resolve templates and process escape sequences
        template_resolved = await resolve_template_variables(hass, text)
        processed_text = template_resolved.replace('\\n', '\n').replace('\\t', '\t')

        # Send text using pypixelcolor
        success = await api.display_text_pypixelcolor(
            text=processed_text,
            color=color,
            font=font,
            animation=animation,
            speed=speed,
            rainbow_mode=rainbow_mode
        )

        if success:
            _LOGGER.info("Text mode update successful: %s (color=#%s, font=%s, anim=%d, speed=%d)",
                       processed_text, color, font, animation, speed)
        else:
            _LOGGER.error("Text mode update failed")

        return success

    except Exception as err:
        _LOGGER.error("Error in text mode update: %s", err)
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