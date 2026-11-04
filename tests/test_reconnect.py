"""Tests for the reconnect watcher."""
from __future__ import annotations

import asyncio

import pytest

from custom_components.ipixel_color import api as api_mod
from custom_components.ipixel_color.bluetooth import client as client_mod

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(client_mod, "RESPONSE_TIMEOUT", 0.01)
    monkeypatch.setattr(client_mod, "REDISCOVERY_ATTEMPTS", 0)
    monkeypatch.setattr(api_mod, "RECONNECT_BACKOFF_START", 0.05)
    monkeypatch.setattr(api_mod, "RECONNECT_BACKOFF_MAX", 60.0)


async def test_advertisement_cuts_backoff_short(
    hass, bluetooth_manager, establish_connection_mock
):
    bluetooth_manager.add_device(ADDRESS)
    api = api_mod.iPIXELAPI(hass, ADDRESS)
    await api.connect()
    await api.start_watcher()
    callback, _ = bluetooth_manager.registered_callbacks[-1]

    # Panel disappears; let a few reconnect attempts fail so the backoff grows.
    del bluetooth_manager.devices[ADDRESS]
    establish_connection_mock[-1].drop()
    await asyncio.sleep(0.4)
    assert not api.is_connected
    assert api._reconnect_task is not None and not api._reconnect_task.done()

    # Panel comes back and advertises: reconnect without waiting out the
    # current backoff (now 0.4 s). Ensure the last attempt is older than the
    # minimum retry interval first.
    while asyncio.get_running_loop().time() - api._last_reconnect_attempt < 0.06:
        await asyncio.sleep(0.01)
    bluetooth_manager.add_device(ADDRESS)
    callback(None, None)
    for _ in range(20):
        if api.is_connected:
            break
        await asyncio.sleep(0.01)
    assert api.is_connected
    await api.stop_watcher()
