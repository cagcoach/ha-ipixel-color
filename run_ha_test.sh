#!/bin/bash
# Home Assistant Simulator Test Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

if [ $# -lt 1 ]; then
    echo "Usage: ./run_ha_test.sh [MAC_ADDRESS] [optional: text]"
    echo "Examples:"
    echo "  ./run_ha_test.sh AA:BB:CC:DD:EE:FF                 # Interactive mode"
    echo "  ./run_ha_test.sh AA:BB:CC:DD:EE:FF 'hello\nworld'  # Send specific text"
    echo "  ./run_ha_test.sh AA:BB:CC:DD:EE:FF full            # Run full test suite"
    exit 1
fi

echo "🏠 Starting Home Assistant Simulator..."
python3 "$SCRIPT_DIR/ha_simulator.py" "$@"