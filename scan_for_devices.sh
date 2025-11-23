#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"
python3 "$SCRIPT_DIR/scan_devices.py"
