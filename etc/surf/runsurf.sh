#!/bin/bash
# Wait for RitaFrame to actually answer before opening the browser.
# A fixed sleep is a race: on a slow boot the browser opens first and then sits
# on "Connection refused" forever, because it never retries.
URL="http://127.0.0.1:8000"
# Generous, because this races the app's cold start: the Pi needed ~70s from boot
# to serving on the first try. The original 90s budget was fine, but a slower boot
# would leave the frame stuck on "Connection refused" with no retry.
TIMEOUT="${SURF_WAIT_TIMEOUT:-300}"
export DISPLAY="${DISPLAY:-:0}"
LOG="${RITAFRAME_LOG:-$HOME/ritaframe.log}"
say() { echo "$(date '+%H:%M:%S') runsurf: $*" | tee -a "$LOG"; }

# Make sure the screen is landscape first, otherwise surf sizes itself to the
# portrait 480x800 the Pi boots into. Idempotent, so running it twice is fine.
if ! "$(dirname "$0")/../rotate-display.sh" >> "$LOG" 2>&1; then
    say "could not set landscape mode; continuing"
fi

waited=0
while [ "$waited" -lt "$TIMEOUT" ]; do
    if curl -sf -o /dev/null --max-time 3 "$URL"; then
        say "RitaFrame is up after ${waited}s, opening $URL"
        exec surf "$URL"
    fi
    sleep 2
    waited=$((waited + 2))
done

say "RitaFrame did not respond within ${TIMEOUT}s; opening anyway to show the error"
exec surf "$URL"
