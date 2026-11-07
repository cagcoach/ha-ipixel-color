"""Test fixtures: stub the Home Assistant / bleak modules this integration
depends on so the reconnect logic can be tested without a running HA or
Bluetooth hardware."""
from __future__ import annotations

import asyncio
import datetime
import enum
import sys
import types

import pytest

# ---------------------------------------------------------------------------
# Minimal stand-ins for the third-party / HA modules the integration imports
# ---------------------------------------------------------------------------


class BleakError(Exception):
    """Stand-in for bleak.exc.BleakError."""


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class HomeAssistantError(Exception):
    """Stand-in for homeassistant.exceptions.HomeAssistantError."""


class ConfigEntryNotReady(Exception):
    """Stand-in for homeassistant.exceptions.ConfigEntryNotReady."""


class BluetoothChange(enum.Enum):
    """Stand-in for bluetooth.BluetoothChange."""

    ADVERTISEMENT = "advertisement"


class BluetoothScanningMode(enum.Enum):
    """Stand-in for bluetooth.BluetoothScanningMode."""

    ACTIVE = "active"


class BluetoothServiceInfoBleak:
    """Stand-in for bluetooth.BluetoothServiceInfoBleak."""


class BLEDevice:
    """Stand-in for a bleak BLEDevice."""

    def __init__(self, address: str, name: str = "LED_BLE_test") -> None:
        self.address = address
        self.name = name


class FakeBleakClient:
    """Stand-in for BleakClientWithServiceCache."""

    def __init__(self, device: BLEDevice, disconnected_callback=None) -> None:
        self._device = device
        self._disconnected_callback = disconnected_callback
        self._connected = True
        self.notify_handler = None
        self.stopped_notify: list[str] = []
        self.started_notify: list[str] = []
        self.written: list[tuple[str, bytes]] = []
        self.disconnect_count = 0
        self.fail_write = False
        self.fail_write_and_drop = False
        self.drop_after_write = False
        self.mtu_size = 247
        self.auto_reply: bytes | None = None
        self.notifying = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def start_notify(self, uuid: str, handler) -> None:
        if self.notifying:
            # BlueZ refuses a second subscription on the same characteristic.
            raise BleakError("[org.bluez.Error.NotPermitted] Notify acquired")
        self.notifying = True
        self.started_notify.append(uuid)
        self.notify_handler = handler

    async def stop_notify(self, uuid: str) -> None:
        self.notifying = False
        self.stopped_notify.append(uuid)

    def notify(self, data: bytes) -> None:
        """Simulate a notification from the panel."""
        if self.notifying and self.notify_handler:
            self.notify_handler("fa03", bytearray(data))

    async def write_gatt_char(self, uuid: str, data: bytes, response: bool = False) -> None:
        if self.fail_write_and_drop:
            # Simulate a write that kills the link (raises and disconnects).
            self._connected = False
            if self._disconnected_callback:
                self._disconnected_callback(self)
            raise BleakError("connection lost during write")
        if self.fail_write:
            raise BleakError("write failed")
        self.written.append((uuid, bytes(data)))
        if self.auto_reply is not None:
            asyncio.get_running_loop().call_soon(self.notify, self.auto_reply)
        if self.drop_after_write:
            self._connected = False
            if self._disconnected_callback:
                self._disconnected_callback(self)

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self._connected = False
        if self._disconnected_callback:
            self._disconnected_callback(self)

    def drop(self) -> None:
        """Simulate an unexpected link drop."""
        self._connected = False
        if self._disconnected_callback:
            self._disconnected_callback(self)


class FakeBluetoothManager:
    """Controllable stand-in for the HA bluetooth API surface."""

    def __init__(self) -> None:
        self.devices: dict[str, BLEDevice] = {}
        self.rediscovered: list[str] = []
        self.registered_callbacks: list[tuple[object, dict]] = []
        self.callback_handles: list[object] = []

    def add_device(self, address: str, name: str = "LED_BLE_test") -> None:
        self.devices[address] = BLEDevice(address, name)

    def async_ble_device_from_address(self, hass, address, connectable=True):
        return self.devices.get(address)

    def async_rediscover_address(self, hass, address) -> None:
        self.rediscovered.append(address)

    def async_register_callback(self, hass, callback, match_dict, mode):
        self.registered_callbacks.append((callback, dict(match_dict)))
        handle = object()
        self.callback_handles.append(handle)
        return lambda: self.callback_handles.remove(handle)


@pytest.fixture
def bluetooth_manager() -> FakeBluetoothManager:
    return FakeBluetoothManager()


# ---------------------------------------------------------------------------
# Package-level stubs (installed once, before any component import)
# ---------------------------------------------------------------------------

_bleak = _module("bleak")
_bleak.exc = _module("bleak.exc", BleakError=BleakError)
sys.modules["bleak.exc"] = _bleak.exc
# Names pypixelcolor imports at module level; tests never use them.
_bleak.BleakClient = type("BleakClient", (), {})
_bleak.BleakScanner = type("BleakScanner", (), {})
_bleak.backends = _module("bleak.backends")
_bleak.backends.device = _module("bleak.backends.device", BLEDevice=type("BLEDevice", (), {}))
sys.modules["bleak.backends"] = _bleak.backends
sys.modules["bleak.backends.device"] = _bleak.backends.device


class BleakClientWithServiceCache:
    """Stand-in for bleak_retry_connector.BleakClientWithServiceCache."""


async def establish_connection(client_type, device, name, disconnected_callback=None, max_attempts=4):
    """Stand-in replaced per-test by the establish_connection_mock fixture."""
    raise NotImplementedError("use establish_connection_mock fixture")


_bleak_retry = _module(
    "bleak_retry_connector",
    BleakClientWithServiceCache=BleakClientWithServiceCache,
    establish_connection=establish_connection,
)
sys.modules["bleak_retry_connector"] = _bleak_retry


class Platform(enum.Enum):
    """Stand-in for homeassistant.const.Platform."""

    SWITCH = "switch"
    TEXT = "text"
    SENSOR = "sensor"
    SELECT = "select"
    NUMBER = "number"
    BUTTON = "button"
    LIGHT = "light"


class Template:
    """Stand-in for homeassistant.helpers.template.Template."""

    def __init__(self, *args, **kwargs) -> None:
        pass


class HomeAssistant:
    """Stand-in for homeassistant.core.HomeAssistant."""


class ConfigEntry:
    """Stand-in for homeassistant.config_entries.ConfigEntry."""


class DeviceInfo:
    """Stand-in for homeassistant.helpers.entity.DeviceInfo."""


class RestoreEntity:
    """Stand-in for homeassistant.helpers.restore_state.RestoreEntity."""


class TextEntity:
    """Stand-in for homeassistant.components.text.TextEntity."""


class TextMode(enum.Enum):
    """Stand-in for homeassistant.components.text.TextMode."""

    TEXT = "text"


_ha = _module("homeassistant")
_ha.exceptions = _module(
    "homeassistant.exceptions",
    HomeAssistantError=HomeAssistantError,
    ConfigEntryNotReady=ConfigEntryNotReady,
)
sys.modules["homeassistant.exceptions"] = _ha.exceptions
_ha.core = _module("homeassistant.core", HomeAssistant=HomeAssistant)
sys.modules["homeassistant.core"] = _ha.core
_ha.const = _module("homeassistant.const", Platform=Platform)
sys.modules["homeassistant.const"] = _ha.const
_ha.config_entries = _module("homeassistant.config_entries", ConfigEntry=ConfigEntry)
sys.modules["homeassistant.config_entries"] = _ha.config_entries
_ha.helpers = _module("homeassistant.helpers")
_ha.helpers.entity = _module("homeassistant.helpers.entity", DeviceInfo=DeviceInfo)
sys.modules["homeassistant.helpers.entity"] = _ha.helpers.entity
_ha.helpers.restore_state = _module(
    "homeassistant.helpers.restore_state", RestoreEntity=RestoreEntity
)
sys.modules["homeassistant.helpers.restore_state"] = _ha.helpers.restore_state
_ha.helpers.template = _module("homeassistant.helpers.template", Template=Template)
sys.modules["homeassistant.helpers.template"] = _ha.helpers.template
_ha.helpers.entity_registry = _module("homeassistant.helpers.entity_registry")
sys.modules["homeassistant.helpers.entity_registry"] = _ha.helpers.entity_registry
_ha.components = _module("homeassistant.components")
_ha.components.text = _module(
    "homeassistant.components.text", TextEntity=TextEntity, TextMode=TextMode
)
sys.modules["homeassistant.components.text"] = _ha.components.text
sys.modules["homeassistant.components"] = _ha.components
sys.modules["homeassistant.helpers"] = _ha.helpers
_ha.util = _module("homeassistant.util")
_ha.util.dt = _module("homeassistant.util.dt", now=datetime.datetime.now)
sys.modules["homeassistant.util"] = _ha.util
sys.modules["homeassistant.util.dt"] = _ha.util.dt
sys.modules["homeassistant"] = _ha

# The bluetooth component is the only one we genuinely need at runtime; it is
# wired to the controllable fake manager below.
_bluetooth_mod = _module("homeassistant.components.bluetooth")
sys.modules["homeassistant.components.bluetooth"] = _bluetooth_mod


def _install_bluetooth_api(manager: FakeBluetoothManager) -> None:
    _bluetooth_mod.async_ble_device_from_address = manager.async_ble_device_from_address
    _bluetooth_mod.async_rediscover_address = manager.async_rediscover_address
    _bluetooth_mod.async_register_callback = manager.async_register_callback
    _bluetooth_mod.BluetoothChange = BluetoothChange
    _bluetooth_mod.BluetoothScanningMode = BluetoothScanningMode
    _bluetooth_mod.BluetoothServiceInfoBleak = BluetoothServiceInfoBleak
    _ha.components.bluetooth = _bluetooth_mod


@pytest.fixture(autouse=True)
def _bluetooth(bluetooth_manager: FakeBluetoothManager):
    """Point the stubbed bluetooth module at a fresh manager per test."""
    _install_bluetooth_api(bluetooth_manager)
    yield bluetooth_manager


class FakeHass:
    """Minimal HomeAssistant stand-in with a real event loop."""

    def __init__(self) -> None:
        self.data: dict = {}
        self._stopping = False

    @property
    def loop(self):
        """Resolve lazily so the fixture can be built before the loop starts."""
        return asyncio.get_event_loop_policy().get_event_loop()

    @property
    def is_stopping(self) -> bool:
        return self._stopping

    def async_create_task(self, coro):
        return self.loop.create_task(coro)


@pytest.fixture
def hass():
    return FakeHass()


@pytest.fixture
def establish_connection_mock(monkeypatch):
    """Replace establish_connection with one that returns FakeBleakClient.

    The client module binds ``establish_connection`` at import time, so we
    patch both the source module and the client module's reference.
    """
    created: list[FakeBleakClient] = []

    async def _establish(client_type, device, name, disconnected_callback=None, max_attempts=4):
        client = FakeBleakClient(device, disconnected_callback)
        created.append(client)
        return client

    monkeypatch.setattr(_bleak_retry, "establish_connection", _establish)
    monkeypatch.setattr(
        _bleak_retry, "BleakClientWithServiceCache", FakeBleakClient
    )
    import custom_components.ipixel_color.bluetooth.client as client_mod

    monkeypatch.setattr(client_mod, "establish_connection", _establish)
    monkeypatch.setattr(client_mod, "BleakClientWithServiceCache", FakeBleakClient)
    return created
