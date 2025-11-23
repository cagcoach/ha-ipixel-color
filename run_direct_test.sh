#!/bin/bash
# Direct text test wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/activate_test_env.sh"

echo "📱 Running Direct Text Test (bypasses device info)"
python3 "$SCRIPT_DIR/direct_text_test.py" "$@"