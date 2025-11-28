"""Command building for iPIXEL Color devices."""
from __future__ import annotations


def make_power_command(on: bool) -> bytes:
    """Build power control command.
    
    Command format from protocol documentation:
    [5, 0, 7, 1, on_byte] where on_byte = 1 for on, 0 for off
    """
    on_byte = 1 if on else 0
    return bytes([5, 0, 7, 1, on_byte])


def make_brightness_command(brightness: int) -> bytes:
    """Build brightness control command.

    Command 0x8004 from ipixel-ctrl set_brightness.py

    Args:
        brightness: Brightness level from 1 to 100

    Returns:
        Command bytes for brightness control

    Raises:
        ValueError: If brightness is not in valid range (1-100)
    """
    if brightness < 1 or brightness > 100:
        raise ValueError("Brightness must be between 1 and 100")

    return make_command_payload(0x8004, bytes([brightness]))


def make_command_payload(opcode: int, payload: bytes) -> bytes:
    """Create command with header (following ipixel-ctrl/common.py format)."""
    total_length = len(payload) + 4  # +4 for length and opcode
    
    command = bytearray()
    command.extend(total_length.to_bytes(2, 'little'))  # Length (little-endian)
    command.extend(opcode.to_bytes(2, 'little'))        # Opcode (little-endian)
    command.extend(payload)                             # Payload data
    
    return bytes(command)