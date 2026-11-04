"""Tests for the cached power state the panel cannot report."""
from __future__ import annotations

from custom_components.ipixel_color import api as api_mod

ADDRESS = "AA:BB:CC:DD:EE:FF"


async def test_power_state_defaults_to_on(hass, bluetooth_manager):
    api = api_mod.iPIXELAPI(hass, ADDRESS)
    assert api.power_state is True


async def test_power_state_can_be_restored(hass, bluetooth_manager):
    api = api_mod.iPIXELAPI(hass, ADDRESS)
    api.restore_power_state(False)
    assert api.power_state is False


async def test_set_power_updates_cached_state(
    hass, bluetooth_manager, establish_connection_mock
):
    bluetooth_manager.add_device(ADDRESS)
    api = api_mod.iPIXELAPI(hass, ADDRESS)
    await api.connect()
    assert await api.set_power(False)
    assert api.power_state is False
