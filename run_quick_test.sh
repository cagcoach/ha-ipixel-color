#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

if [ $# -lt 1 ]; then
    echo "Usage: ./run_quick_test.sh [MAC_ADDRESS] [TEXT]"
    echo "Example: ./run_quick_test.sh AA:BB:CC:DD:EE:FF 'Hello World'"
    exit 1
fi

python3 "$SCRIPT_DIR/quick_test.py" "$@"
