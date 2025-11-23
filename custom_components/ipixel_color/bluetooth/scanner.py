"""Bluetooth device discovery for iPIXEL Color devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak import BleakScanner
from bleak.exc import BleakError

from ..const import DEVICE_NAME_PREFIX

_LOGGER = logging.getLogger(__name__)


async def discover_ipixel_devices(timeout: int = 10, return_all: bool = False) -> list[dict[str, Any]]:
    """Discover iPIXEL devices via Bluetooth scanning.
    
    Args:
        timeout: Scan duration in seconds
        return_all: If True, return all devices with compatibility indication
        
    Returns:
        List of discovered device information with is_compatible flag
    """
    _LOGGER.debug("Starting iPIXEL device discovery using static discovery method, return_all=%s", return_all)
    devices = []

    try:
        # Use BleakScanner.discover() instead of callbacks to avoid HA conflicts
        _LOGGER.debug("Using BleakScanner.discover() with timeout=%d", timeout)
        discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
        
        _LOGGER.debug("BleakScanner.discover() returned %d devices", len(discovered))
        
        for address, (device, adv_data) in discovered.items():
            device_name = device.name or f"Unknown_{address[-4:]}"
            _LOGGER.debug("Checking device: %s (%s)", device_name, device.address)
            
            # Check if device is compatible (starts with our prefix)
            is_compatible = bool(device.name and device.name.startswith(DEVICE_NAME_PREFIX))
            
            device_info = {
                "address": device.address,
                "name": device_name,
                "rssi": adv_data.rssi,
                "is_compatible": is_compatible,
            }
            
            # Include device if it's compatible OR if we want all devices
            if is_compatible or return_all:
                devices.append(device_info)
                if is_compatible:
                    _LOGGER.info("Found compatible iPIXEL device: %s", device_info)
                else:
                    _LOGGER.debug("Found other device: %s", device_info)
        
        _LOGGER.debug("Discovery completed, found %d total devices (%d compatible)", 
                     len(devices), sum(1 for d in devices if d.get('is_compatible', False)))
        return devices
        
    except BleakError as err:
        _LOGGER.error("Discovery failed: %s", err)
        return []
    except Exception as err:
        _LOGGER.error("Unexpected discovery error: %s", err)
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return []