"""Command building for iPIXEL Color devices."""
from __future__ import annotations

from zlib import crc32


def make_power_command(on: bool) -> bytes:
    """Build power control command.
    
    Command format from protocol documentation:
    [5, 0, 7, 1, on_byte] where on_byte = 1 for on, 0 for off
    """
    on_byte = 1 if on else 0
    return bytes([5, 0, 7, 1, on_byte])


def make_diy_mode_command(mode: int = 1) -> bytes:
    """Build DIY mode command.
    
    Mode 1 = enter and clear current, show new
    """
    return bytes([5, 0, 4, 1, mode])


def make_default_mode_command() -> bytes:
    """Build default mode command to exit slideshow.
    
    Command 0x8003 from ipixel-ctrl set_default_mode.py
    """
    return make_command_payload(0x8003, bytes())


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


def make_png_command(png_data: bytes, buffer_number: int = 1) -> bytes:
    """Build PNG display command.
    
    Following ipixel-ctrl write_data_png.py exactly.
    """
    data_size = len(png_data)
    data_crc = crc32(png_data) & 0xFFFFFFFF
    
    # Build payload
    payload = bytearray()
    payload.append(0x00)  # Fixed byte
    payload.extend(data_size.to_bytes(4, 'little'))  # Data size
    payload.extend(data_crc.to_bytes(4, 'little'))   # CRC32
    payload.append(0x00)  # Fixed byte  
    payload.append(buffer_number)  # Buffer number (screen 1)
    payload.extend(png_data)  # PNG data
    
    # Build complete command
    command = bytearray()
    total_length = len(payload) + 4  # +4 for length(2) + command(2)
    command.extend(total_length.to_bytes(2, 'little'))  # Length
    command.extend([0x02, 0x00])  # Command 0x0002
    command.extend(payload)  # Payload
    
    return bytes(command)


def make_command_payload(opcode: int, payload: bytes) -> bytes:
    """Create command with header (following ipixel-ctrl/common.py format)."""
    total_length = len(payload) + 4  # +4 for length and opcode
    
    command = bytearray()
    command.extend(total_length.to_bytes(2, 'little'))  # Length (little-endian)
    command.extend(opcode.to_bytes(2, 'little'))        # Opcode (little-endian)
    command.extend(payload)                             # Payload data
    
    return bytes(command)