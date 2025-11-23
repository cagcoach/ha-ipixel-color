#!/usr/bin/env python3
"""
Bluetooth device scanner for iPIXEL devices
"""
import asyncio
import logging
from bleak import BleakScanner

logging.basicConfig(level=logging.WARNING)  # Reduce noise

async def scan_for_ipixel_devices():
    print("🔍 Scanning for iPIXEL devices (LED_BLE_*)...")
    print("=" * 50)
    
    found_devices = []
    
    def detection_callback(device, advertisement_data):
        if device.name and device.name.startswith("LED_BLE_"):
            found_devices.append({
                "name": device.name,
                "address": device.address,
                "rssi": advertisement_data.rssi
            })
            print(f"📱 Found: {device.name}")
            print(f"   📍 MAC: {device.address}")
            print(f"   📶 RSSI: {advertisement_data.rssi} dBm")
            print("-" * 30)
    
    # Scan for 10 seconds
    try:
        scanner = BleakScanner(detection_callback)
        await scanner.start()
        await asyncio.sleep(10)
        await scanner.stop()
    except Exception as e:
        print(f"❌ Scan error: {e}")
        return []
    
    if found_devices:
        print(f"\n✅ Found {len(found_devices)} iPIXEL device(s)")
        print("\nTo test, use one of these commands:")
        for device in found_devices:
            print(f"  python3 quick_test.py {device['address']} 'Hello'")
    else:
        print("❌ No iPIXEL devices found")
        print("\nTroubleshooting:")
        print("- Make sure your iPIXEL device is powered on")
        print("- Ensure Bluetooth is enabled on your Mac")
        print("- Try moving closer to the device")
        print("- Check if device is in pairing mode")
    
    return found_devices

if __name__ == "__main__":
    asyncio.run(scan_for_ipixel_devices())
