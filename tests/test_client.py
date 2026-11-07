"""Tests for the Bluetooth client and device-info handling."""
from __future__ import annotations

import asyncio

import pytest

from custom_components.ipixel_color.bluetooth import client as client_mod
from custom_components.ipixel_color.bluetooth.client import BluetoothClient
from custom_components.ipixel_color.exceptions import iPIXELConnectionError

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.fixture(autouse=True)
def _fast_timeouts(monkeypatch):
    monkeypatch.setattr(client_mod, "RESPONSE_TIMEOUT", 0.05)


async def _connected_client(hass, bluetooth_manager, establish_connection_mock):
    bluetooth_manager.add_device(ADDRESS)
    client = BluetoothClient(hass, ADDRESS)
    received: list[bytes] = []
    await client.connect(lambda sender, data: received.append(bytes(data)))
    return client, establish_connection_mock[-1], received


async def test_notifications_subscribed_once(hass, bluetooth_manager, establish_connection_mock):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    for _ in range(3):
        assert await client.send_command(b"\x05\x00\x07\x01\x01")
    assert len(fake.started_notify) == 1
    assert fake.stopped_notify == []


async def test_request_returns_response_and_forwards_to_handler(
    hass, bluetooth_manager, establish_connection_mock
):
    client, fake, received = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.auto_reply = b"\x0b\x00\x01\x80\x85"
    response = await client.request(b"\x08\x00\x01\x80", timeout=1.0)
    assert response == b"\x0b\x00\x01\x80\x85"
    assert received == [b"\x0b\x00\x01\x80\x85"]
    assert client._listeners == []


async def test_request_without_response_returns_none(
    hass, bluetooth_manager, establish_connection_mock
):
    client, _, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    assert await client.request(b"\x01", timeout=0.01) is None


async def test_large_payload_is_chunked_to_mtu(hass, bluetooth_manager, establish_connection_mock):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.mtu_size = 100
    payload = bytes(range(256)) * 4
    assert await client.send_command(payload)
    chunks = [data for _, data in fake.written]
    assert all(len(c) <= 97 for c in chunks)
    assert b"".join(chunks) == payload


async def test_chunk_size_capped_and_floored(hass, bluetooth_manager, establish_connection_mock):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.mtu_size = 517
    assert client._chunk_size() == client_mod.MAX_CHUNK_SIZE
    fake.mtu_size = None
    assert client._chunk_size() == client_mod.MIN_CHUNK_SIZE


async def test_concurrent_commands_do_not_interleave(
    hass, bluetooth_manager, establish_connection_mock
):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.mtu_size = 23  # 20-byte chunks
    a = b"A" * 100
    b = b"B" * 100
    await asyncio.gather(client.send_command(a), client.send_command(b))
    joined = b"".join(data for _, data in fake.written)
    assert joined in (a + b, b + a)


async def test_write_failure_returns_false(hass, bluetooth_manager, establish_connection_mock):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.fail_write = True
    assert await client.send_command(b"\x01") is False


async def test_link_drop_mid_write_raises_connection_error(
    hass, bluetooth_manager, establish_connection_mock
):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    fake.fail_write_and_drop = True
    with pytest.raises(iPIXELConnectionError):
        await client.send_command(b"\x01")


async def test_send_when_disconnected_raises(hass, bluetooth_manager, establish_connection_mock):
    client = BluetoothClient(hass, ADDRESS)
    with pytest.raises(iPIXELConnectionError):
        await client.send_command(b"\x01")


async def test_connection_count_increments(hass, bluetooth_manager, establish_connection_mock):
    client, fake, _ = await _connected_client(hass, bluetooth_manager, establish_connection_mock)
    assert client.connection_count == 1
    fake.drop()
    assert await client.ensure_connected()
    assert client.connection_count == 2
