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

# How long to wait for HA's Bluetooth manager to (re)discover the device
# after a connection drop before giving up on the current attempt.
REDISCOVERY_ATTEMPTS = 3
REDISCOVERY_DELAY = 1.0

# Writes are split into chunks no larger than the negotiated ATT payload
# (MTU - 3) and capped at 244 bytes, matching pypixelcolor's own client.
# Sending a whole frame in one unacknowledged write overflows the panel's
# buffer on Bluetooth proxies and long payloads are silently dropped.
MAX_CHUNK_SIZE = 244
MIN_CHUNK_SIZE = 20

# How long to wait for the panel to acknowledge a command.
RESPONSE_TIMEOUT = 2.0


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
        self._connect_lock = asyncio.Lock()
        # Serializes writes so chunks from two commands never interleave.
        self._write_lock = asyncio.Lock()
        # Temporary listeners for command responses. Notifications are
        # subscribed ONCE per connection (see _dispatch_notification); a
        # second start_notify on the same characteristic fails on BlueZ with
        # "Notify acquired", which broke device-info queries.
        self._listeners: list[Callable[[Any, bytearray], None]] = []
        # Incremented on every successful connection.
        self.connection_count = 0
        # Optional hook invoked (sync) when the link drops unexpectedly; the
        # API layer uses it to schedule a reconnect instead of leaving the
        # device dead until the integration is reloaded.
        self.on_disconnect: Callable[[], None] | None = None

    def _disconnected_callback(self, client: BleakClientWithServiceCache) -> None:
        """Called when device disconnects."""
        was_connected = self._connected
        self._connected = False
        _LOGGER.warning("iPIXEL device %s disconnected", self._address)
        if was_connected and self.on_disconnect is not None:
            self.on_disconnect()

    def _dispatch_notification(self, sender: Any, data: bytearray) -> None:
        """Single persistent notify callback that fans out to all consumers."""
        for listener in list(self._listeners):
            try:
                listener(sender, data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Notification listener error: %s", err)
        if self._notification_handler is not None:
            try:
                self._notification_handler(sender, data)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Notification handler error: %s", err)

    async def _get_ble_device(self):
        """Return the BLEDevice, triggering rediscovery when the cache is stale.

        After a connection drop HA's Bluetooth manager may briefly lose track
        of the device even though it is still advertising (the panel is
        physically fine — the link just died). Ask the manager to re-scan for
        the address before giving up on the current attempt.
        """
        ble_device = bluetooth.async_ble_device_from_address(
            self._hass, self._address, connectable=True
        )
        if ble_device:
            return ble_device

        _LOGGER.debug(
            "Device %s not in Bluetooth cache, triggering rediscovery",
            self._address,
        )
        bluetooth.async_rediscover_address(self._hass, self._address)
        for _ in range(REDISCOVERY_ATTEMPTS):
            await asyncio.sleep(REDISCOVERY_DELAY)
            ble_device = bluetooth.async_ble_device_from_address(
                self._hass, self._address, connectable=True
            )
            if ble_device:
                return ble_device
        return None

    async def connect(self, notification_handler: Callable[[Any, bytearray], None]) -> bool:
        """Connect to the iPIXEL device.

        Args:
            notification_handler: Callback for device notifications

        Returns:
            True if connected successfully

        Raises:
            iPIXELConnectionError: If connection fails
        """
        async with self._connect_lock:
            return await self._connect_locked(notification_handler)

    async def _connect_locked(
        self, notification_handler: Callable[[Any, bytearray], None]
    ) -> bool:
        """Connect while holding the connect lock."""
        _LOGGER.debug("Connecting to iPIXEL device at %s", self._address)

        try:
            # Get BLEDevice from Home Assistant's Bluetooth integration
            ble_device = await self._get_ble_device()

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
            try:
                await self._client.start_notify(NOTIFY_UUID, self._dispatch_notification)
            except BleakError:
                # A connection that cannot deliver notifications is useless;
                # tear it down so the next attempt starts from a clean slate.
                self._connected = False
                try:
                    await self._client.disconnect()
                except BleakError:
                    pass
                self._client = None
                raise
            self.connection_count += 1
            _LOGGER.info("Successfully connected to iPIXEL device")
            return True

        except BleakError as err:
            _LOGGER.error("Failed to connect to %s: %s", self._address, err)
            raise iPIXELConnectionError(f"Connection failed: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error connecting to %s: %s", self._address, err)
            raise iPIXELConnectionError(f"Connection failed: {err}") from err

    async def ensure_connected(self) -> bool:
        """Return True if connected, reconnecting when the link was lost.

        Unlike ``connect()`` this never raises: it is the reconnect-aware
        entry point used by entity action paths. Concurrent callers are
        serialized through the connect lock so a drop cannot trigger a
        stampede of connection attempts.
        """
        if self.is_connected:
            return True
        if self._notification_handler is None:
            return False
        async with self._connect_lock:
            if self.is_connected:
                return True
            try:
                return await self._connect_locked(self._notification_handler)
            except iPIXELConnectionError as err:
                _LOGGER.warning(
                    "Reconnect to %s failed: %s", self._address, err
                )
                return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._connected:
            try:
                await self._client.stop_notify(NOTIFY_UUID)
                await self._client.disconnect()
                _LOGGER.debug("Disconnected from iPIXEL device")
            except Exception as err:  # noqa: BLE001 - never let teardown raise
                _LOGGER.error("Error during disconnect: %s", err)
            finally:
                self._connected = False
                self._client = None  # Don't reuse client - create fresh for next connection
                self._listeners.clear()

    def _chunk_size(self) -> int:
        """Return the write chunk size for the current connection."""
        mtu = getattr(self._client, "mtu_size", None)
        if not isinstance(mtu, int) or mtu <= 3:
            return MIN_CHUNK_SIZE
        return max(MIN_CHUNK_SIZE, min(MAX_CHUNK_SIZE, mtu - 3))

    async def request(self, command: bytes, timeout: float | None = None) -> bytes | None:
        """Write a command and return the first notification it produces.

        The command is written in acknowledged chunks. Returns None when the
        panel sends nothing back within ``timeout`` (many commands are not
        acknowledged), which is not treated as an error.

        Raises:
            iPIXELConnectionError: If not connected, or the link dies mid-write.
            BleakError: If a write fails while the link stays up.
        """
        if not self.is_connected or not self._client:
            raise iPIXELConnectionError("Device not connected")
        if timeout is None:
            timeout = RESPONSE_TIMEOUT

        async with self._write_lock:
            client = self._client
            responses: list[bytes] = []
            received = asyncio.Event()

            def listener(sender: Any, data: bytearray) -> None:
                responses.append(bytes(data))
                received.set()

            self._listeners.append(listener)
            try:
                chunk_size = self._chunk_size()
                _LOGGER.debug(
                    "Sending command (%d bytes, %d-byte chunks): %s",
                    len(command),
                    chunk_size,
                    command[:32].hex(),
                )
                try:
                    for pos in range(0, len(command), chunk_size):
                        await client.write_gatt_char(
                            WRITE_UUID, command[pos : pos + chunk_size], response=True
                        )
                except BleakError as err:
                    # A write failure on a link that is no longer up means the
                    # connection died mid-command; surface it as a connection
                    # error so callers can reconnect and retry.
                    if not self.is_connected:
                        raise iPIXELConnectionError(
                            f"Connection lost during command: {err}"
                        ) from err
                    raise

                try:
                    await asyncio.wait_for(received.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    _LOGGER.debug("No response within %.1f seconds", timeout)
                    return None
                _LOGGER.debug("Command response: %s", responses[0].hex())
                return responses[0]
            finally:
                if listener in self._listeners:
                    self._listeners.remove(listener)

    async def send_command(self, command: bytes) -> bool:
        """Send a command to the device.

        Returns:
            True if the command was written, False if a write failed.

        Raises:
            iPIXELConnectionError: If not connected, or the link dies mid-write.
        """
        try:
            await self.request(command)
        except BleakError as err:
            _LOGGER.error("Failed to send command: %s", err)
            return False
        return True

    @property
    def is_connected(self) -> bool:
        """Return True if connected to device."""
        return self._connected and self._client and self._client.is_connected

    @property
    def address(self) -> str:
        """Return device address."""
        return self._address
