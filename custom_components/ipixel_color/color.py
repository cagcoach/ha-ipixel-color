"""Base color entity for iPIXEL Color integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

if TYPE_CHECKING:
    from .api import iPIXELAPI

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Utility functions for color conversion
def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., 'ffffff' or '#ffffff')

    Returns:
        Tuple of (red, green, blue) values from 0-255

    Raises:
        ValueError: If hex_color is invalid format
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')

    if len(hex_color) != 6:
        raise ValueError(f"Invalid hex color length: {hex_color} (expected 6 characters)")

    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    except ValueError as e:
        raise ValueError(f"Invalid hex color format: {hex_color}") from e


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB tuple to hex color string.

    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)

    Returns:
        Hex color string (e.g., 'ffffff')
    """
    return f"{r:02x}{g:02x}{b:02x}"


def hex_to_rgb_normalized(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color string to normalized RGB tuple.

    Args:
        hex_color: Hex color string (e.g., 'ffffff')

    Returns:
        Tuple of (red, green, blue) values from 0.0-1.0
    """
    r, g, b = hex_to_rgb(hex_color)
    return (r / 255.0, g / 255.0, b / 255.0)


class iPIXELColorBase(TextEntity, RestoreEntity):
    """Base class for iPIXEL Color entities (text color, background color, etc.)."""

    _attr_mode = TextMode.TEXT
    _attr_native_max = 6  # 6 hex characters for RGB color
    _attr_pattern = r"^[0-9A-Fa-f]{6}$"  # Validate hex color format

    # Override these in subclasses
    _color_name: str = "Color"  # e.g., "Text Color", "Background Color"
    _entity_suffix: str = "color"  # e.g., "text_color", "background_color"
    _default_color: str = "ffffff"  # Default color value
    _trigger_modes: list[str] = []  # Modes that trigger auto-update

    def __init__(
        self,
        hass: HomeAssistant,
        api: "iPIXELAPI",
        entry: ConfigEntry,
        address: str,
        name: str
    ) -> None:
        """Initialize the color input."""
        self.hass = hass
        self._api = api
        self._entry = entry
        self._address = address
        self._name = name
        self._attr_name = f"{name} {self._color_name}"
        self._attr_unique_id = f"{address}_{self._entity_suffix}"
        self._current_value = self._default_color

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
        if last_state is not None and last_state.state:
            self._current_value = last_state.state
            _LOGGER.debug("Restored %s: %s", self._color_name.lower(), self._current_value)

    @property
    def native_value(self) -> str | None:
        """Return the current color value."""
        return self._current_value

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    def get_hex(self) -> str:
        """Get color as hex string (e.g., 'ffffff')."""
        return self._current_value

    def get_rgb(self) -> tuple[int, int, int]:
        """Get color as RGB tuple (0-255, 0-255, 0-255).

        Returns:
            Tuple of (red, green, blue) values from 0-255
        """
        try:
            return hex_to_rgb(self._current_value)
        except ValueError:
            _LOGGER.error("Invalid color format: %s", self._current_value)
            return (255, 255, 255)  # Default to white

    def get_rgb_normalized(self) -> tuple[float, float, float]:
        """Get color as normalized RGB tuple (0.0-1.0, 0.0-1.0, 0.0-1.0).

        Returns:
            Tuple of (red, green, blue) values from 0.0-1.0
        """
        try:
            return hex_to_rgb_normalized(self._current_value)
        except ValueError:
            _LOGGER.error("Invalid color format: %s", self._current_value)
            return (1.0, 1.0, 1.0)  # Default to white

    async def async_set_value(self, value: str) -> None:
        """Set the color value."""
        # Validate hex color format
        import re
        if not re.match(r"^[0-9A-Fa-f]{6}$", value):
            _LOGGER.error("Invalid hex color format: %s (expected 6 hex digits)", value)
            return

        self._current_value = value.lower()
        _LOGGER.debug("%s set to: #%s", self._color_name, self._current_value)

        # Trigger auto-update if enabled and in appropriate mode
        await self._trigger_auto_update()

    async def _trigger_auto_update(self) -> None:
        """Trigger display update if auto-update is enabled and in appropriate mode."""
        if not self._trigger_modes:
            return

        try:
            from .common import update_ipixel_display

            # Check if we're in one of the trigger modes
            mode_entity_id = f"select.{self._name.lower().replace(' ', '_')}_mode"
            mode_state = self.hass.states.get(mode_entity_id)

            if mode_state and mode_state.state in self._trigger_modes:
                # Check auto-update setting
                auto_update_entity_id = f"switch.{self._name.lower().replace(' ', '_')}_auto_update"
                auto_update_state = self.hass.states.get(auto_update_entity_id)

                if auto_update_state and auto_update_state.state == "on":
                    await update_ipixel_display(self.hass, self._name, self._api)
                    _LOGGER.debug("Auto-update triggered due to %s change", self._color_name.lower())
        except Exception as err:
            _LOGGER.debug("Could not trigger auto-update: %s", err)
