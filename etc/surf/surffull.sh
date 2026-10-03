#!/bin/bash
# Put the frame in fullscreen kiosk mode: browser fullscreen, desktop chrome gone.
#
# Three things the original version got wrong:
#   1. `sleep 30` then a blind `xdotool key F11` sends F11 to whatever is focused,
#      which at boot is the terminal running run.sh, not the browser.
#   2. `xdotool key --window <id>` delivers a *synthetic* event, and surf ignores
#      those. The key has to go through XTEST to the activated window instead.
#   3. F11 is a toggle, so firing it blindly un-fullscreens a window that is already
#      fullscreen. This checks the current state first and only acts if needed.
#
# It also has to clear the window stacking: LXDE's desktop and panel sit *above*
# surf, so fullscreen alone still leaves them covering the frame.
#
# Run from ~/.config/lxsession/LXDE-pi/autostart.

export DISPLAY="${DISPLAY:-:0}"
# Generous, because this runs concurrently with the app's own cold start. The Pi
# took ~70s from boot to serving on the first try; the original 90s budget expired
# just before the browser appeared and the frame was left windowed.
TIMEOUT="${FULLSCREEN_WAIT_TIMEOUT:-300}"
# Terminals are unmapped rather than killed so they can be shown again for
# debugging. run.sh tees to ~/ritaframe.log, so nothing is lost.
HIDE_TERMINALS="${KIOSK_HIDE_TERMINALS:-1}"

# This script runs without a terminal now, so log to the same file as the app.
LOG="${RITAFRAME_LOG:-$HOME/ritaframe.log}"
say() { echo "$(date '+%H:%M:%S') fullscreen: $*" | tee -a "$LOG"; }

# surf opens more than one window: a 10x10 helper and the real one. Picking the
# largest is not enough on its own -- right after launch only the helper exists
# yet, so it would win and F11 would be aimed at a 10x10 window. Require a
# realistically sized window before accepting it.
find_surf_window() {
    for w in $(xdotool search --class surf 2>/dev/null); do
        eval "$(xdotool getwindowgeometry --shell "$w" 2>/dev/null)"
        [ "$WIDTH" -ge 100 ] 2>/dev/null && [ "$HEIGHT" -ge 100 ] 2>/dev/null || continue
        echo "$((WIDTH * HEIGHT)) $w"
    done | sort -rn | head -1 | cut -d' ' -f2
}

is_fullscreen() {
    xprop -id "$1" _NET_WM_STATE 2>/dev/null | grep -q FULLSCREEN
}

waited=0
wid=""
while [ "$waited" -lt "$TIMEOUT" ]; do
    wid="$(find_surf_window)"
    [ -n "$wid" ] && break
    sleep 2
    waited=$((waited + 2))
done

if [ -z "$wid" ]; then
    say "surf window did not appear within ${TIMEOUT}s"
    exit 1
fi

if is_fullscreen "$wid"; then
    say "already fullscreen"
else
    # Raise and focus first, otherwise openbox can route the keystroke elsewhere.
    xdotool windowraise "$wid" 2>/dev/null
    xdotool windowactivate --sync "$wid" 2>/dev/null
    sleep 1
    # XTEST event to the focused window -- no --window flag.
    xdotool key --clearmodifiers F11
    sleep 2
    if is_fullscreen "$wid"; then
        say "surf is fullscreen ($(xdotool getwindowname "$wid" 2>/dev/null))"
    else
        geom="$(xdotool getwindowgeometry --shell "$wid" 2>/dev/null | grep -E '^(X|Y|WIDTH|HEIGHT)=' | tr '\n' ' ')"
        say "F11 had no effect on window $wid ($geom)"
        exit 1
    fi
fi

# Clear the desktop chrome that would otherwise cover the browser.
# LXDE re-maps the panel and desktop shortly after login, so this runs a few
# times rather than once, and finishes by lifting surf above whatever is left.
#
# Note this only ever runs *after* the browser is confirmed fullscreen. If the app
# failed to start there is no browser, so the run.sh terminal stays on screen
# showing the error -- which is exactly what you want to see.
for attempt in 1 2 3; do
    for class in lxpanel pcmanfm; do
        for w in $(xdotool search --class "$class" 2>/dev/null); do
            eval "$(xdotool getwindowgeometry --shell "$w" 2>/dev/null)"
            # Skip the 10x10 helper windows, but hide the real full-width ones.
            [ "$WIDTH" -gt 100 ] && xdotool windowunmap "$w" 2>/dev/null
        done
    done

    if [ "$HIDE_TERMINALS" = "1" ]; then
        for w in $(xdotool search --class lxterminal 2>/dev/null); do
            xdotool windowunmap "$w" 2>/dev/null
            # openbox happily re-maps an unmapped window, so also park it off the
            # left edge of the screen where it cannot cover the frame.
            xdotool windowmove "$w" -900 0 2>/dev/null
        done
    fi

    xdotool windowraise "$wid" 2>/dev/null
    [ "$attempt" -lt 3 ] && sleep 3
done

# Verify the browser is genuinely the topmost, viewable window.
top="$(xprop -root _NET_CLIENT_LIST_STACKING 2>/dev/null | grep -oE '0x[0-9a-f]+' | tail -1)"
if [ "$top" = "$(printf '0x%x' "$wid")" ]; then
    say "kiosk mode set, browser is topmost"
else
    say "browser is not topmost (topmost=$top, browser=$(printf '0x%x' "$wid"))"
    exit 1
fi
