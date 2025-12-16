"""Bluetooth client management for iPIXEL Color devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, TYPE_CHECKING

from bleak.exc import BleakError
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
        self._notification_handler: Callable | None = None

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
        _LOGGER.debug("Connecting to iPIXEL device at %s", self._address)

        try:
            # Get BLEDevice from Home Assistant's Bluetooth integration
            ble_device = bluetooth.async_ble_device_from_address(
                self._hass, self._address, connectable=True
            )

            if not ble_device:
                raise iPIXELConnectionError(
                    f"Device {self._address} not found. "
                    "Ensure the device is powered on and in range."
                )

            # Use establish_connection with service caching for reliable connection
            # This handles retries, timeouts, and works with Bluetooth proxies
            _LOGGER.debug("Establishing connection to %s using bleak-retry-connector", self._address)
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                ble_device.name or "iPIXEL Display",
                disconnected_callback=self._disconnected_callback,
                max_attempts=3,
            )

            self._connected = True

            # Store and enable notifications
            self._notification_handler = notification_handler
            await self._client.start_notify(NOTIFY_UUID, notification_handler)
            _LOGGER.info("Successfully connected to iPIXEL device")
            return True

        except BleakError as err:
            _LOGGER.error("Failed to connect to %s: %s", self._address, err)
            raise iPIXELConnectionError(f"Connection failed: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error connecting to %s: %s", self._address, err)
            raise iPIXELConnectionError(f"Connection failed: {err}") from err

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(NOTIFY_UUID)
                await self._client.disconnect()
                _LOGGER.debug("Disconnected from iPIXEL device")
            except BleakError as err:
                _LOGGER.error("Error during disconnect: %s", err)
            finally:
                self._connected = False
                self._client = None  # Don't reuse client - create fresh for next connection

    async def send_command(self, command: bytes) -> bool:
        """Send command to the device and log any response.

        Args:
            command: Command bytes to send

        Returns:
            True if command was sent successfully

        Raises:
            iPIXELConnectionError: If not connected
        """
        import time

        if not self._connected or not self._client:
            raise iPIXELConnectionError("Device not connected")

        command_size = len(command)
        start_time = time.perf_counter()

        try:
            # Set up temporary response capture
            response_data = []
            response_received = asyncio.Event()

            def response_handler(sender: Any, data: bytearray) -> None:
                response_data.append(bytes(data))
                response_received.set()
                _LOGGER.info("Device response: %s", data.hex())

            # Stop existing notifications first to avoid "already enabled" error
            try:
                await self._client.stop_notify(NOTIFY_UUID)
            except (KeyError, BleakError) as e:
                # No callback was registered yet, which is fine
                _LOGGER.debug("Could not stop notifications (not started): %s", e)

            # Enable notifications to capture response
            await self._client.start_notify(NOTIFY_UUID, response_handler)

            try:
                _LOGGER.debug("Sending command: %s", command.hex())
                await self._client.write_gatt_char(WRITE_UUID, command)

                # Wait for response with short timeout
                try:
                    await asyncio.wait_for(response_received.wait(), timeout=2.0)
                    if response_data:
                        _LOGGER.info("Command response received: %s", response_data[-1].hex())
                    else:
                        _LOGGER.debug("No response received within timeout")
                except asyncio.TimeoutError:
                    _LOGGER.debug("No response received within 2 seconds")

            finally:
                # Restore the original notification handler
                try:
                    await self._client.stop_notify(NOTIFY_UUID)
                except (KeyError, BleakError) as e:
                    _LOGGER.debug("Could not stop notifications in cleanup: %s", e)

                if self._notification_handler:
                    try:
                        await self._client.start_notify(NOTIFY_UUID, self._notification_handler)
                    except BleakError as e:
                        _LOGGER.warning("Could not restart original notification handler: %s", e)

            elapsed_time = time.perf_counter() - start_time
            throughput = command_size / elapsed_time if elapsed_time > 0 else 0
            _LOGGER.debug(
                "BLE send: %d bytes in %.1f ms (%.1f KB/s)",
                command_size, elapsed_time * 1000, throughput / 1024
            )
            return True
        except BleakError as err:
            elapsed_time = time.perf_counter() - start_time
            _LOGGER.error("Failed to send command (%d bytes) after %.1f ms: %s", command_size, elapsed_time * 1000, err)
            return False

    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._connected and self._client and self._client.is_connected

    @property
    def address(self) -> str:
        """Return device address."""
        return self._address
