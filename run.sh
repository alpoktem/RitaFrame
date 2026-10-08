#!/bin/bash
cd "$(dirname "$0")" || exit 1

# Set to False to quieten logging
export DEBUG_MODE="${DEBUG_MODE:-False}"

LOG="${RITAFRAME_LOG:-$HOME/ritaframe.log}"

# Sync time once at startup. The Pi has no RTC; systemd-timesyncd alone took an
# hour to correct the clock after boot, so nudge it to sync straight away and
# the app just keeps the system time from there on.
(
  sleep 5
  sudo systemctl restart systemd-timesyncd 2>/dev/null || true
  echo "boot-time-sync: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG"
) &

# Fail loudly on a missing dependency. Without this the app exits silently and the
# browser just shows "Connection refused", which is hard to trace back to setup.
missing=()
for module in flask requests yaml; do
    python3 -c "import $module" 2>/dev/null || missing+=("$module")
done
if [ ${#missing[@]} -gt 0 ]; then
    msg="RitaFrame cannot start: missing Python module(s): ${missing[*]}
Install them with: python3 -m pip install --user -r requirements.txt"
    echo "$msg"
    echo "$msg" >> "$LOG"
    # Keep the terminal open on failure so the message is readable on the frame.
    echo "(terminal kept open - press Ctrl+C to close)"
    sleep 3600
    exit 1
fi

# Log to a file too: the kiosk hides terminals, so stdout alone would be lost.
echo "--- RitaFrame starting $(date '+%Y-%m-%d %H:%M:%S') ---" >> "$LOG"
python3 -u app.py 2>&1 | tee -a "$LOG"