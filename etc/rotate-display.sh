#!/bin/bash
# Force the frame to landscape.
#
# The Pi's HDMI output comes up rotated 90 degrees (480x800 portrait) even though
# the panel is physically landscape, which leaves everything sideways. This resets
# it to a landscape mode and re-applies it on every boot.
#
# Run from ~/.config/autostart, and again from runsurf.sh before the browser opens.
#
# To flip the frame upside down (cable input at the bottom) set ROTATION=inverted,
# either here or in the environment when running this script. Valid values are the
# xrandr rotations: normal, left, right, inverted.

export DISPLAY="${DISPLAY:-:0}"
ROTATION="${ROTATION:-normal}"

case "$ROTATION" in
    normal|left|right|inverted) ;;
    *) echo "rotate-display: ROTATION must be normal|left|right|inverted (got '$ROTATION')"; exit 1 ;;
esac

# Give X a moment to create the output on a cold boot.
for _ in $(seq 1 20); do
    [ -n "$(xrandr -q 2>/dev/null)" ] && break
    sleep 1
done

# Prefer the connected output, falling back to the first one xrandr reports.
OUTPUT="$(xrandr -q 2>/dev/null | awk '/ connected/ {print $1; exit}')"
[ -z "$OUTPUT" ] && { echo "rotate-display: no connected output found"; exit 1; }

# Pick the active mode (marked '*') when it is landscape, else the first landscape
# mode listed. Each mode line looks like "   800x480   60.00*+", so the mode is
# field 1 -- not field 2.
MODE="$(xrandr -q | awk -v out="$OUTPUT" '
    $1 == out && $2 == "connected" { inout = 1; next }
    inout && $1 ~ /^[0-9]+x[0-9]+$/ {
        split($1, d, "x")
        if (d[1] > d[2]) {
            n++
            modes[n] = $1
            if ($2 ~ /\*/) active = n
        }
    }
    END { print (active ? modes[active] : modes[1]) }
')"

if [ -z "$MODE" ]; then
    echo "rotate-display: no landscape mode found for $OUTPUT, leaving rotation alone"
    exit 1
fi

xrandr --output "$OUTPUT" --mode "$MODE" --rotate "$ROTATION" && \
    echo "rotate-display: $OUTPUT set to $MODE, rotation $ROTATION"
