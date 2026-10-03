#!/bin/bash
# Wait for RitaFrame to actually answer before opening the browser.
# A fixed sleep is a race: on a slow boot the browser opens first and then sits
# on "Connection refused" forever, because it never retries.
URL="http://127.0.0.1:8000"
TIMEOUT="${SURF_WAIT_TIMEOUT:-90}"

waited=0
while [ "$waited" -lt "$TIMEOUT" ]; do
    if curl -sf -o /dev/null --max-time 3 "$URL"; then
        echo "RitaFrame is up after ${waited}s, opening $URL"
        exec surf "$URL"
    fi
    sleep 2
    waited=$((waited + 2))
done

echo "RitaFrame did not respond within ${TIMEOUT}s; opening anyway to show the error"
exec surf "$URL"
