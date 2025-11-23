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
