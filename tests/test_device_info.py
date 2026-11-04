"""Tests for device-info querying in the API layer."""
from __future__ import annotations

import pytest

from custom_components.ipixel_color import api as api_mod
from custom_components.ipixel_color.bluetooth import client as client_mod

ADDRESS = "AA:BB:CC:DD:EE:FF"
INFO = {"width": 64, "height": 20, "device_type": 133, "device_type_str": "Type 133"}


@pytest.fixture(autouse=True)
def _stubs(monkeypatch):
    monkeypatch.setattr(client_mod, "RESPONSE_TIMEOUT", 0.05)
    monkeypatch.setattr(api_mod, "build_device_info_command", lambda: b"\x08\x00\x01\x80")
    monkeypatch.setattr(api_mod, "parse_device_response", lambda data: dict(INFO))


async def _api(hass, bluetooth_manager):
    bluetooth_manager.add_device(ADDRESS)
    api = api_mod.iPIXELAPI(hass, ADDRESS)
    await api.connect()
    return api


async def test_device_info_read_over_existing_subscription(
    hass, bluetooth_manager, establish_connection_mock
):
    api = await _api(hass, bluetooth_manager)
    fake = establish_connection_mock[-1]
    fake.auto_reply = b"\x0b\x00\x01\x80\x85"
    info = await api.get_device_info()
    assert info["width"] == 64 and info["height"] == 20
    # The connect-time subscription is reused, not re-acquired.
    assert len(fake.started_notify) == 1


async def test_fallback_not_kept_across_reconnect(
    hass, bluetooth_manager, establish_connection_mock, monkeypatch
):
    api = await _api(hass, bluetooth_manager)
    real_request = api._bluetooth.request

    async def short_request(command, timeout=5.0):
        return await real_request(command, timeout=0.01)

    monkeypatch.setattr(api._bluetooth, "request", short_request)

    fallback = await api.get_device_info()
    assert (fallback["width"], fallback["height"]) == (64, 16)
    # Same connection: defaults reused without another query.
    writes = len(establish_connection_mock[-1].written)
    assert await api.get_device_info() is fallback
    assert len(establish_connection_mock[-1].written) == writes

    # After a reconnect the panel answers and the real size is used.
    establish_connection_mock[-1].drop()
    assert await api.ensure_connected()
    establish_connection_mock[-1].auto_reply = b"\x0b\x00\x01\x80\x85"
    info = await api.get_device_info()
    assert (info["width"], info["height"]) == (64, 20)
