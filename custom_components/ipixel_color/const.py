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
MODE_TIMER = "timer"

AVAILABLE_MODES = [
    MODE_TEXT_IMAGE,
    MODE_TEXT,
    MODE_CLOCK,
    MODE_TIMER,
]

DEFAULT_MODE = MODE_TEXT_IMAGE