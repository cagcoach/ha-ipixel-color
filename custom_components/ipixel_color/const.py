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
CONF_DISPLAY_WIDTH = "display_width"
CONF_DISPLAY_HEIGHT = "display_height"

DEVICE_TYPE_BYTE_TO_LED_TYPE = {
    128: 0,
    129: 2,
    130: 4,
    131: 3,
    132: 1,
    133: 5,
    134: 6,
    135: 7,
    136: 8,
    137: 9,
    138: 10,
    139: 11,
    140: 12,
    141: 13,
    142: 14,
    143: 15,
    144: 16,
    145: 17,
    146: 18,
    147: 19,
}

LED_TYPE_SPECS = {
    0: {"width": 64, "height": 64, "device_type": 128, "name": "64x64"},
    1: {"width": 96, "height": 16, "device_type": 132, "name": "96x16"},
    2: {"width": 32, "height": 32, "device_type": 129, "name": "32x32"},
    3: {"width": 64, "height": 16, "device_type": 131, "name": "64x16"},
    4: {"width": 32, "height": 16, "device_type": 130, "name": "32x16"},
    5: {"width": 64, "height": 20, "device_type": 133, "name": "64x20"},
    6: {"width": 128, "height": 32, "device_type": 134, "name": "128x32"},
    7: {"width": 144, "height": 16, "device_type": 135, "name": "144x16"},
    8: {"width": 192, "height": 16, "device_type": 136, "name": "192x16"},
    9: {"width": 48, "height": 24, "device_type": 137, "name": "48x24"},
    10: {"width": 64, "height": 32, "device_type": 138, "name": "64x32"},
    11: {"width": 96, "height": 32, "device_type": 139, "name": "96x32"},
    12: {"width": 128, "height": 32, "device_type": 140, "name": "128x32"},
    13: {"width": 96, "height": 32, "device_type": 141, "name": "96x32"},
    14: {"width": 160, "height": 32, "device_type": 142, "name": "160x32"},
    15: {"width": 192, "height": 32, "device_type": 143, "name": "192x32"},
    16: {"width": 256, "height": 32, "device_type": 144, "name": "256x32"},
    17: {"width": 320, "height": 32, "device_type": 145, "name": "320x32"},
    18: {"width": 384, "height": 32, "device_type": 146, "name": "384x32"},
    19: {"width": 448, "height": 32, "device_type": 147, "name": "448x32"},
}

DISPLAY_SIZE_TO_LED_TYPE = {
    (spec["width"], spec["height"]): led_type
    for led_type, spec in LED_TYPE_SPECS.items()
}

DEFAULT_DISPLAY_WIDTH = 64
DEFAULT_DISPLAY_HEIGHT = 16

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
