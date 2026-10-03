#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Set to False to quieten logging
export DEBUG_MODE="${DEBUG_MODE:-False}"

python3 -u app.py