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