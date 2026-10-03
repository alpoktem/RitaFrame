#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Set to False to quieten logging
export DEBUG_MODE="${DEBUG_MODE:-False}"

# Fail loudly on a missing dependency. Without this the app exits silently and the
# browser just shows "Connection refused", which is hard to trace back to setup.
missing=()
for module in flask requests yaml; do
    python3 -c "import $module" 2>/dev/null || missing+=("$module")
done
if [ ${#missing[@]} -gt 0 ]; then
    echo "RitaFrame cannot start: missing Python module(s): ${missing[*]}"
    echo "Install them with: python3 -m pip install --user -r requirements.txt"
    echo "(keep the terminal open to see this message)"
    exit 1
fi

python3 -u app.py
