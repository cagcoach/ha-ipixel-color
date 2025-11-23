"""Bluetooth client management for iPIXEL Color devices."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from bleak import BleakClient
from bleak.exc import BleakError

# Note: bleak-retry-connector requires BLEDevice objects, 
# but we only have MAC address strings, so we use standard BleakClient

from ..const import WRITE_UUID, NOTIFY_UUID, CONNECTION_TIMEOUT
from ..exceptions import iPIXELConnectionError, iPIXELTimeoutError

_LOGGER = logging.getLogger(__name__)


class BluetoothClient:
    """Manages Bluetooth connection and communication."""
    
    def __init__(self, address: str) -> None:
        """Initialize Bluetooth client."""
        self._address = address
        self._client: BleakClient | None = None
        self._connected = False
        self._notification_handler: Callable | None = None

    def _disconnected_callback(self, client: BleakClient) -> None:
        """Called when device disconnects."""
        _LOGGER.warning("iPIXEL device %s disconnected", self._address)
        self._connected = False
        
    async def connect(self, notification_handler: Callable[[Any, bytearray], None]) -> bool:
        """Connect to the iPIXEL device.
        
        Args:
            notification_handler: Callback for device notifications
            
        Returns:
            True if connected successfully
        """
        _LOGGER.debug("Connecting to iPIXEL device at %s", self._address)
        
        try:
            # Always use standard BleakClient for simplicity
            # bleak-retry-connector requires a BLEDevice object which we don't have
            _LOGGER.debug("Connecting with BleakClient to %s", self._address)
            self._client = BleakClient(self._address, disconnected_callback=self._disconnected_callback)
            await asyncio.wait_for(
                self._client.connect(), timeout=CONNECTION_TIMEOUT
            )
            
            self._connected = True
            
            # Store and enable notifications
            self._notification_handler = notification_handler
            await self._client.start_notify(NOTIFY_UUID, notification_handler)
            _LOGGER.info("Successfully connected to iPIXEL device")
            return True
            
        except asyncio.TimeoutError as err:
            _LOGGER.error("Connection timeout to %s: %s", self._address, err)
            raise iPIXELTimeoutError(f"Connection timeout: {err}") from err
        except BleakError as err:
            _LOGGER.error("Failed to connect to %s: %s", self._address, err)
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
    
    async def send_command(self, command: bytes) -> bool:
        """Send command to the device and log any response.
        
        Args:
            command: Command bytes to send
            
        Returns:
            True if command was sent successfully
        """
        if not self._connected or not self._client:
            raise iPIXELConnectionError("Device not connected")

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
            except KeyError:
                # No callback was registered yet, which is fine
                pass

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
                await self._client.stop_notify(NOTIFY_UUID)
                if self._notification_handler:
                    await self._client.start_notify(NOTIFY_UUID, self._notification_handler)
            
            return True
        except BleakError as err:
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