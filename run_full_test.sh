#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

if [ $# -lt 1 ]; then
    echo "Usage: ./run_full_test.sh [MAC_ADDRESS]"
    echo "Example: ./run_full_test.sh AA:BB:CC:DD:EE:FF"
    exit 1
fi

python3 "$SCRIPT_DIR/test_wrapper.py" "$@"
