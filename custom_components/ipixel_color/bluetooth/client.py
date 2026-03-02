"""Bluetooth client management for iPIXEL Color devices - Buffer-safe version."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TYPE_CHECKING

from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from homeassistant.components import bluetooth
from ..const import WRITE_UUID, NOTIFY_UUID
from ..exceptions import iPIXELConnectionError

_LOGGER = logging.getLogger(__name__)


class BluetoothClient:
    """Manages Bluetooth connection and communication."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize Bluetooth client.

        Args:
            hass: Home Assistant instance
            address: Bluetooth MAC address
        """
        self._hass = hass
        self._address = address
        self._client: BleakClientWithServiceCache | None = None
        self._connected = False

    def _disconnected_callback(self, client: BleakClientWithServiceCache) -> None:
        """Called when device disconnects."""
        _LOGGER.warning("iPIXEL device %s disconnected", self._address)
        self._connected = False

    async def connect(self, notification_handler: Callable[[Any, bytearray], None]) -> bool:
        """Connect to the iPIXEL device.

        Args:
            notification_handler: Callback for device notifications

        Returns:
            True if connected successfully

        Raises:
            iPIXELConnectionError: If connection fails
        """
        # If already connected, return success
        if self._connected and self._client and self._client.is_connected:
            return True

        # Get BLEDevice from Home Assistant's Bluetooth integration
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if not ble_device:
            raise iPIXELConnectionError(f"Device {self._address} not found.")

        # Establish connection with retries
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            ble_device.name or "iPIXEL Display",
            disconnected_callback=self._disconnected_callback,
            max_attempts=3,
        )

        # Enable notifications and mark as connected
        await self._client.start_notify(NOTIFY_UUID, notification_handler)
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(NOTIFY_UUID)
                await self._client.disconnect()
                _LOGGER.debug("Disconnected from iPIXEL device")
            except Exception as err:
                _LOGGER.error("Error during disconnect: %s", err)
            finally:
                self._connected = False
                self._client = None

    async def send_command(self, command: bytes) -> bool:
        """Send command to the device in chunks with buffer management.

        Args:
            command: Command bytes to send

        Returns:
            True if command was sent successfully, False otherwise
        """
        if not self._connected or not self._client:
            return False

        try:
            chunk_size = 20

            # Clear buffer for large commands
            if len(command) > 100:
                await self._client.write_gatt_char(WRITE_UUID, b"\x00" * 20, response=True)
                await asyncio.sleep(0.1)

            # Send command in chunks with delays
            for i in range(0, len(command), chunk_size):
                await self._client.write_gatt_char(
                    WRITE_UUID,
                    command[i : i + chunk_size],
                    response=True,
                )
                await asyncio.sleep(0.05)

            return True

        except Exception as err:
            _LOGGER.error("Failed to send command: %s", err)
            return False

    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._connected and self._client and self._client.is_connected

    @property
    def address(self) -> str:
        """Return device address."""
        return self._address
