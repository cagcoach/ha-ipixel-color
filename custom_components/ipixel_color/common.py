"""Common utilities for iPIXEL Color integration."""
from __future__ import annotations

import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.helpers import entity_registry as er
from .const import MODE_TEXT_IMAGE, MODE_TEXT, MODE_CLOCK, DOMAIN

_LOGGER = logging.getLogger(__name__)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB tuple to hex color string."""
    return f"{r:02x}{g:02x}{b:02x}"


def get_color_from_light_entity(hass: HomeAssistant, address: str, entity_suffix: str, default: str | None = None) -> str | None:
    """Get hex color from a light entity.

    Args:
        hass: Home Assistant instance
        address: Device address
        entity_suffix: Entity suffix (e.g., 'text_color', 'background_color')
        default: Default color if entity not found or off (None means no color/transparent)

    Returns:
        Hex color string (e.g., 'ffffff') or None if light is off/not found
    """
    entity_id = get_entity_id_by_unique_id(hass, address, entity_suffix, "light")
    state = hass.states.get(entity_id) if entity_id else None

    if not state:
        return default

    # If light is off, return black
    if state.state == "off":
        return "000000"

    if state.attributes.get("rgb_color"):
        r, g, b = state.attributes["rgb_color"]
        # Apply brightness
        brightness = state.attributes.get("brightness", 255)
        factor = brightness / 255.0
        return rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))

    return default


def get_entity_id_by_unique_id(hass: HomeAssistant, address: str, entity_suffix: str, platform: str = None) -> str | None:
    """Get entity_id from unique_id using the entity registry.

    Args:
        hass: Home Assistant instance
        address: Device address (e.g., '5c1592bd')
        entity_suffix: Entity suffix (e.g., 'text_color', 'background_color', 'mode_select')
        platform: Optional platform filter (e.g., 'light', 'select', 'switch')

    Returns:
        Entity ID if found, None otherwise
    """
    registry = er.async_get(hass)
    unique_id = f"{address}_{entity_suffix}"

    # Look up entity by unique_id
    for entity_id, entry in registry.entities.items():
        if entry.unique_id == unique_id and entry.platform == DOMAIN:
            # If platform specified, verify it matches
            if platform and not entity_id.startswith(f"{platform}."):
                continue
            return entity_id

    return None


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
        mode = await _get_entity_setting(hass, device_name, "select", "mode_select", str, api._address)
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
            text_entity_id = get_entity_id_by_unique_id(hass, api._address, "text_display", "text")
            text_state = hass.states.get(text_entity_id) if text_entity_id else None
            if not text_state or text_state.state in ("unknown", "unavailable", ""):
                _LOGGER.warning("No text to display - skipping update")
                return False
            text = text_state.state
        
        # Get all current settings
        font_name = await _get_entity_setting(hass, device_name, "select", "font_select", str, api._address)
        font_size = await _get_entity_setting(hass, device_name, "number", "font_size", float, api._address)
        line_spacing = await _get_entity_setting(hass, device_name, "number", "line_spacing", int, api._address)
        antialias = await _get_entity_setting(hass, device_name, "switch", "antialiasing", bool, api._address)

        # Get color settings from light entities
        text_color = get_color_from_light_entity(hass, api._address, "text_color", default="ffffff")
        _LOGGER.debug("Text color: #%s", text_color)

        bg_color = get_color_from_light_entity(hass, api._address, "background_color", default="000000")
        _LOGGER.debug("Background color: #%s", bg_color)

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
        clock_style = await _get_entity_setting(hass, device_name, "select", "clock_style_select", int, api._address)
        if clock_style is None:
            clock_style = 1  # Default style

        format_24 = await _get_entity_setting(hass, device_name, "switch", "clock_24h", bool, api._address)
        if format_24 is None:
            format_24 = True  # Default to 24h

        show_date = await _get_entity_setting(hass, device_name, "switch", "clock_show_date", bool, api._address)
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
            text_entity_id = get_entity_id_by_unique_id(hass, api._address, "text_display", "text")
            text_state = hass.states.get(text_entity_id) if text_entity_id else None
            if not text_state or text_state.state in ("unknown", "unavailable", ""):
                _LOGGER.warning("No text to display - skipping update")
                return False
            text = text_state.state

        # Get pypixelcolor text settings (reusing existing entities where possible)

        # Reuse existing font selector - convert TTF filename to full path
        font_name = await _get_entity_setting(hass, device_name, "select", "font_select", str, api._address)
        if font_name and font_name.endswith(('.ttf', '.otf')):
            # Custom TTF/OTF font from fonts/ folder
            from pathlib import Path
            font_path = Path(__file__).parent / "fonts" / font_name
            font = str(font_path) if font_path.exists() else "CUSONG"
        else:
            # Use pypixelcolor's built-in fonts or default
            font = "CUSONG"

        # Get text color from light entity
        color = get_color_from_light_entity(hass, api._address, "text_color", default="ffffff")
        if color == "000000":
            color = "010000"  # Use near-black instead of pure black for text mode
        _LOGGER.debug("Text mode - text color: #%s", color)

        # Get background color from light entity
        bg_color = get_color_from_light_entity(hass, api._address, "background_color", default=None)
        _LOGGER.debug("Text mode - background color: %s", f"#{bg_color}" if bg_color else "none")

        # Animation - need new number entity
        animation = await _get_entity_setting(hass, device_name, "number", "text_animation", int, api._address)
        if animation is None:
            animation = 0  # Default to no animation

        # Speed - need new number entity
        speed = await _get_entity_setting(hass, device_name, "number", "text_speed", int, api._address)
        if speed is None:
            speed = 80  # Default speed

        # Rainbow mode - need new number entity
        rainbow_mode = await _get_entity_setting(hass, device_name, "number", "text_rainbow", int, api._address)
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
            bg_color=bg_color,
            font=font,
            animation=animation,
            speed=speed,
            rainbow_mode=rainbow_mode
        )

        if success:
            _LOGGER.info("Text mode update successful: %s (color=#%s, bg=%s, font=%s, anim=%d, speed=%d)",
                       processed_text, color, f"#{bg_color}" if bg_color else "none", font, animation, speed)
        else:
            _LOGGER.error("Text mode update failed")

        return success

    except Exception as err:
        _LOGGER.error("Error in text mode update: %s", err)
        return False


async def _get_entity_setting(hass: HomeAssistant, device_name: str, platform: str, setting: str, value_type=str, address: str = None):
    """Get setting from Home Assistant entity.

    Args:
        hass: Home Assistant instance
        device_name: Device name for entity ID (fallback if address not provided)
        platform: Platform type (select, number, switch)
        setting: Setting name (font, font_size, etc.)
        value_type: Type to convert value to
        address: Device address for entity registry lookup (preferred)

    Returns:
        Entity value or appropriate default
    """
    try:
        # Try entity registry lookup first if address provided
        entity_id = None
        if address:
            entity_id = get_entity_id_by_unique_id(hass, address, setting, platform)

        # Fallback to manual construction if not found
        if not entity_id:
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