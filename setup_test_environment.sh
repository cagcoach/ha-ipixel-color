#!/bin/bash
set -e

# iPIXEL Color Test Environment Setup Script
# This script sets up everything needed to test the integration standalone

echo "🚀 Setting up iPIXEL Color test environment..."
echo "================================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/test_venv"

echo -e "${BLUE}📁 Working directory: $SCRIPT_DIR${NC}"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed${NC}"
    echo "Please install Python 3 first:"
    echo "  brew install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✅ Found $PYTHON_VERSION${NC}"

# Create virtual environment
echo -e "${BLUE}🔧 Creating virtual environment...${NC}"
if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists, removing old one...${NC}"
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✅ Virtual environment created${NC}"

# Activate virtual environment
echo -e "${BLUE}🔌 Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
pip install --upgrade pip

# Install required packages
echo -e "${BLUE}📦 Installing required packages...${NC}"
pip install bleak>=0.20.0
pip install pillow>=10.0.0

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Check Bluetooth availability on macOS
echo -e "${BLUE}🔵 Checking Bluetooth availability...${NC}"
if system_profiler SPBluetoothDataType > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Bluetooth system available${NC}"
else
    echo -e "${YELLOW}⚠️  Cannot access Bluetooth system info${NC}"
fi

# Make scripts executable
echo -e "${BLUE}🔐 Making scripts executable...${NC}"
chmod +x "$SCRIPT_DIR/test_wrapper.py"
chmod +x "$SCRIPT_DIR/quick_test.py"

# Create activation script
echo -e "${BLUE}📝 Creating activation script...${NC}"
cat > "$SCRIPT_DIR/activate_test_env.sh" << 'EOF'
#!/bin/bash
# Activation script for iPIXEL test environment

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/test_venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found. Run setup_test_environment.sh first."
    exit 1
fi

echo "🔌 Activating iPIXEL test environment..."
source "$VENV_DIR/bin/activate"
echo "✅ Test environment activated!"
echo ""
echo "Available commands:"
echo "  python3 quick_test.py [MAC_ADDRESS] [TEXT]"
echo "  python3 test_wrapper.py [MAC_ADDRESS]"
echo ""
echo "To find your device MAC address:"
echo "  python3 scan_devices.py"
echo ""
echo "To deactivate: deactivate"
EOF

chmod +x "$SCRIPT_DIR/activate_test_env.sh"

# Create device scanner script
echo -e "${BLUE}📡 Creating device scanner...${NC}"
cat > "$SCRIPT_DIR/scan_devices.py" << 'EOF'
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
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    
    try:
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
EOF

chmod +x "$SCRIPT_DIR/scan_devices.py"

# Create convenience wrapper scripts
echo -e "${BLUE}📝 Creating convenience scripts...${NC}"

# Quick test wrapper
cat > "$SCRIPT_DIR/run_quick_test.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

if [ $# -lt 1 ]; then
    echo "Usage: ./run_quick_test.sh [MAC_ADDRESS] [TEXT]"
    echo "Example: ./run_quick_test.sh AA:BB:CC:DD:EE:FF 'Hello World'"
    exit 1
fi

python3 "$SCRIPT_DIR/quick_test.py" "$@"
EOF

# Full test wrapper
cat > "$SCRIPT_DIR/run_full_test.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

if [ $# -lt 1 ]; then
    echo "Usage: ./run_full_test.sh [MAC_ADDRESS]"
    echo "Example: ./run_full_test.sh AA:BB:CC:DD:EE:FF"
    exit 1
fi

python3 "$SCRIPT_DIR/test_wrapper.py" "$@"
EOF

# Device scanner wrapper  
cat > "$SCRIPT_DIR/scan_for_devices.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"
python3 "$SCRIPT_DIR/scan_devices.py"
EOF

chmod +x "$SCRIPT_DIR/run_quick_test.sh"
chmod +x "$SCRIPT_DIR/run_full_test.sh" 
chmod +x "$SCRIPT_DIR/scan_for_devices.sh"

# Test the environment
echo -e "${BLUE}🧪 Testing environment...${NC}"
python3 -c "
import bleak
import PIL
print('✅ bleak imported successfully')
print('✅ PIL version:', PIL.__version__)
print('✅ All dependencies working!')
"

echo ""
echo -e "${GREEN}🎉 Setup complete!${NC}"
echo "================================"
echo ""
echo "📖 Quick start guide:"
echo ""
echo -e "${YELLOW}1. Find your iPIXEL device:${NC}"
echo "   ./scan_for_devices.sh"
echo ""
echo -e "${YELLOW}2. Quick test:${NC}"
echo "   ./run_quick_test.sh [MAC_ADDRESS] 'Hello'"
echo ""
echo -e "${YELLOW}3. Full test suite:${NC}"
echo "   ./run_full_test.sh [MAC_ADDRESS]"
echo ""
echo -e "${YELLOW}4. Manual activation:${NC}"
echo "   source activate_test_env.sh"
echo "   python3 quick_test.py [MAC_ADDRESS] [TEXT]"
echo ""
echo -e "${BLUE}📁 Created files:${NC}"
echo "   test_venv/           - Virtual environment"
echo "   activate_test_env.sh - Environment activation"
echo "   scan_devices.py      - Device discovery"
echo "   scan_for_devices.sh  - Device scanner wrapper"
echo "   run_quick_test.sh    - Quick test wrapper"
echo "   run_full_test.sh     - Full test wrapper"
echo ""
echo -e "${GREEN}✨ Ready to test!${NC}"