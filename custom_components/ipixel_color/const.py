"""Constants for the iPIXEL Color integration."""

DOMAIN = "ipixel_color"
DEFAULT_NAME = "iPIXEL Display"

# Bluetooth UUIDs from protocol documentation
WRITE_UUID = "0000fa02-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fa03-0000-1000-8000-00805f9b34fb"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

# Device discovery
DEVICE_NAME_PREFIX = "LED_BLE_"

# Configuration keys
CONF_ADDRESS = "address"
CONF_NAME = "name"

# Options keys (configurable via the integration's options flow)
# Override the dimensions reported by firmware. Some panels (notably the
# B.K. Light 32x32 sold at Action) advertise wrong dimensions (64x16) and
# only render correctly when the host sends frames at the actual size.
# 0 means "use firmware-reported value".
OPT_OVERRIDE_DIMENSIONS = "override_dimensions"
OPT_PANEL_WIDTH = "panel_width"
OPT_PANEL_HEIGHT = "panel_height"

# Update interval
SCAN_INTERVAL = 30

# Connection settings
CONNECTION_TIMEOUT = 10
RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 1  # seconds between retry attempts

# Display modes (based on pypixelcolor capabilities)
MODE_TEXT_IMAGE = "textimage"
MODE_TEXT = "text"
MODE_CLOCK = "clock"

AVAILABLE_MODES = [
    MODE_TEXT_IMAGE,
    MODE_TEXT,
    MODE_CLOCK,
]

DEFAULT_MODE = MODE_TEXT_IMAGE

# Text-mode animations (pypixelcolor send_text, documented at
# https://lucagoc.fr/pypixelcolor/main/commands/content/). Shown as
# "<number> <name>" so the protocol value stays visible.
TEXT_ANIMATIONS = {
    0: "Static",
    1: "Scroll left",
    2: "Scroll right",
    3: "Scroll up",
    4: "Scroll down",
    5: "Blink",
    6: "Fade",
    7: "Snowflake",
}
TEXT_ANIMATION_OPTIONS = [f"{value} {label}" for value, label in TEXT_ANIMATIONS.items()]
DEFAULT_TEXT_ANIMATION = TEXT_ANIMATION_OPTIONS[0]


def text_animation_value(option: str | None) -> int:
    """Return the animation number for a select option such as "1 Scroll left"."""
    try:
        value = int(str(option).split(" ", 1)[0])
    except (TypeError, ValueError):
        return 0
    return value if value in TEXT_ANIMATIONS else 0


def text_animation_option(value: int) -> str:
    """Return the select option for an animation number."""
    return TEXT_ANIMATION_OPTIONS[value] if value in TEXT_ANIMATIONS else DEFAULT_TEXT_ANIMATION
