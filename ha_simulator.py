#!/usr/bin/env python3
"""
Home Assistant Simulator for iPIXEL Color Integration Testing
This module simulates a complete Home Assistant environment for testing the iPIXEL integration.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import Mock

# Add the custom component to Python path
sys.path.insert(0, str(Path(__file__).parent / "custom_components"))
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

# Reduce bleak noise
logging.getLogger("bleak.backends.corebluetooth").setLevel(logging.WARNING)

# Import after path setup
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.bluetooth import _bluetooth_manager
from ipixel_color import async_setup_entry
from ipixel_color.api import iPIXELAPI


class HASimulator:
    """Simulates Home Assistant environment for testing iPIXEL integration."""
    
    def __init__(self, device_address: str):
        self.device_address = device_address
        self.hass = self._create_hass()
        self.config_entry = self._create_config_entry()
        self.entities = {}
        self.api: Optional[iPIXELAPI] = None
        
    def _create_hass(self) -> HomeAssistant:
        """Create a mock Home Assistant instance."""
        hass = HomeAssistant()
        hass.data = {}
        hass.states = Mock()
        hass.bus = Mock()
        hass.services = Mock()
        
        # Add entity registry mock
        hass.helpers = Mock()
        hass.helpers.entity_registry = Mock()
        
        return hass
        
    def _create_config_entry(self) -> ConfigEntry:
        """Create a mock config entry."""
        return ConfigEntry(
            domain="ipixel_color",
            title="iPIXEL Color",
            data={
                "address": self.device_address,
                "name": "Test iPIXEL"
            }
        )
        
    async def setup_integration(self) -> bool:
        """Set up the iPIXEL integration like Home Assistant would."""
        try:
            print("🔧 Setting up iPIXEL Color integration...")
            
            # Call the integration setup
            result = await async_setup_entry(self.hass, self.config_entry)
            
            if result:
                # Get the API instance from the integration data - stored directly as API object
                if "ipixel_color" in self.hass.data and self.config_entry.entry_id in self.hass.data["ipixel_color"]:
                    self.api = self.hass.data["ipixel_color"][self.config_entry.entry_id]
                    print("✅ Integration setup successful")
                    return True
            
            print("❌ Integration setup failed")
            return False
            
        except Exception as e:
            print(f"💥 Integration setup error: {e}")
            return False
    
    async def connect_device(self) -> bool:
        """Check device connection (already connected during setup)."""
        if not self.api:
            print("❌ API not available - run setup_integration first")
            return False
            
        if self.api.is_connected:
            print(f"✅ Device already connected to {self.device_address}")
            return True
        else:
            print(f"❌ Device not connected to {self.device_address}")
            return False
    
    async def get_device_info(self) -> Optional[Dict[str, Any]]:
        """Get device information."""
        if not self.api or not self.api.is_connected:
            print("❌ Device not connected")
            return None
            
        try:
            print("📊 Getting device information...")
            info = await self.api.get_device_info()
            
            if info:
                print("✅ Device info retrieved:")
                for key, value in info.items():
                    print(f"   📏 {key}: {value}")
                return info
            else:
                print("❌ Failed to get device info")
                return None
                
        except Exception as e:
            print(f"💥 Device info error: {e}")
            return None
    
    async def test_power_control(self) -> bool:
        """Test power control functionality."""
        if not self.api or not self.api.is_connected:
            print("❌ Device not connected")
            return False
            
        try:
            print("⚡ Testing power control...")
            
            # Test power on
            print("🔆 Turning ON...")
            success_on = await self.api.set_power(True)
            if success_on:
                print("✅ Power ON successful")
            else:
                print("❌ Power ON failed")
                
            await asyncio.sleep(1)
            
            # Test power off
            print("🔅 Turning OFF...")
            success_off = await self.api.set_power(False)
            if success_off:
                print("✅ Power OFF successful")
            else:
                print("❌ Power OFF failed")
                
            await asyncio.sleep(1)
            
            # Turn back on for other tests
            print("🔆 Turning back ON...")
            await self.api.set_power(True)
            
            return success_on and success_off
            
        except Exception as e:
            print(f"💥 Power control error: {e}")
            return False
    
    async def send_text(self, text: str) -> bool:
        """Send text to display - simulates text entity functionality."""
        if not self.api or not self.api.is_connected:
            print("❌ Device not connected")
            return False
            
        try:
            print(f"📝 Sending text: '{text.replace(chr(10), '\\n')}'")
            success = await self.api.display_text(text)
            
            if success:
                print("✅ Text sent successfully")
                return True
            else:
                print("❌ Text sending failed")
                return False
                
        except Exception as e:
            print(f"💥 Text sending error: {e}")
            return False
    
    async def run_full_test_suite(self):
        """Run complete test suite like Home Assistant would."""
        print("🎯 Running Full Home Assistant Simulation Test Suite")
        print("=" * 60)
        
        # Setup integration
        if not await self.setup_integration():
            return False
            
        # Connect device
        if not await self.connect_device():
            return False
            
        # Get device info
        device_info = await self.get_device_info()
        if not device_info:
            return False
            
        # Test power control
        await self.test_power_control()
        
        # Test text display with various texts
        test_texts = [
            "Hello",
            "hello\nworld", 
            "Test\nMultiple\nLines",
            "This is a longer text that should auto-scale",
            "🎉 Emoji Test",
            "iPIXEL\nWorking!"
        ]
        
        print("\n📝 Testing Text Display:")
        for i, text in enumerate(test_texts, 1):
            print(f"\n📤 Test {i}:")
            await self.send_text(text)
            await asyncio.sleep(2)  # Wait to see result
            
        return True
    
    async def interactive_mode(self):
        """Interactive mode for manual testing."""
        print("\n🎮 Interactive Mode - Home Assistant Text Entity Simulation")
        print("Commands: 'quit' to exit, 'power on/off' for power control")
        print("=" * 60)
        
        while True:
            try:
                text = input("\n📝 Enter text to display (like HA text entity): ").strip()
                
                if text.lower() in ['quit', 'exit', 'q']:
                    break
                elif text.lower() == 'power on':
                    success = await self.api.set_power(True)
                    print("✅ Power ON" if success else "❌ Power ON failed")
                elif text.lower() == 'power off':
                    success = await self.api.set_power(False)
                    print("✅ Power OFF" if success else "❌ Power OFF failed")
                elif text:
                    await self.send_text(text)
                    
            except KeyboardInterrupt:
                print("\n👋 Exiting...")
                break
            except Exception as err:
                print(f"💥 Error: {err}")
    
    async def cleanup(self):
        """Clean up resources."""
        print("\n🧹 Cleaning up resources...")
        
        if self.api:
            try:
                await self.api.disconnect()
                print("✅ Device disconnected")
            except Exception as e:
                print(f"⚠️  Disconnect error: {e}")
                
        # Clean up bluetooth manager
        await _bluetooth_manager.cleanup_client(self.device_address)


async def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python ha_simulator.py [MAC_ADDRESS] [optional: text]")
        print("Example: python ha_simulator.py AA:BB:CC:DD:EE:FF 'Hello World'")
        sys.exit(1)
        
    address = sys.argv[1]
    
    simulator = HASimulator(address)
    
    try:
        # Setup and connect
        if not await simulator.setup_integration():
            return
            
        if not await simulator.connect_device():
            return
            
        # Get device info
        await simulator.get_device_info()
        
        # If text provided as argument, send it and exit
        if len(sys.argv) > 2:
            text = sys.argv[2]
            await simulator.send_text(text)
        else:
            # Run full test or interactive mode
            choice = input("\n🎮 Run [f]ull test suite or [i]nteractive mode? (f/i): ")
            if choice.lower().startswith('i'):
                await simulator.interactive_mode()
            else:
                await simulator.run_full_test_suite()
                
    except Exception as e:
        print(f"💥 Simulator error: {e}")
    finally:
        await simulator.cleanup()
        print("\n🏁 Home Assistant simulation complete!")


if __name__ == "__main__":
    asyncio.run(main())