"""Weather glyphs as inline SVG rather than emoji.

Emoji were the obvious choice and they render fine on a Mac, but the Pi has no emoji
font installed at all (`fc-list | grep -c emoji` returns 0), so every glyph came out
as an empty box on the frame. It also varies by browser: some build the colour layer
from a different font than the shape, so a glyph can appear monochrome or vanish
while the same character works elsewhere. Both problems are solved by not depending
on a font being present, so these are plain paths in the document.

They draw with `currentColor` so they follow the frame's text colour, and they are
static markup, which matters on a Zero: no font lookup and no per-character shaping.
"""

_SUN = (
    '<circle cx="26" cy="26" r="8.5" fill="currentColor"/>'
    '<g stroke="currentColor" stroke-width="3" stroke-linecap="round">'
    '<path d="M26 9v6M26 37v6M9 26h6M37 26h6M14.1 14.1l4.2 4.2M33.7 33.7l4.2 4.2'
    'M37.9 14.1l-4.2 4.2M18.3 33.7l-4.2 4.2"/>'
    '</g>'
)

# A cloud as a union of circles and a rounded base. Composed rather than one path so
# the shape stays obviously a cloud at a glance from across a room.
_CLOUD = (
    '<g fill="currentColor">'
    '<circle cx="25" cy="33" r="11"/>'
    '<circle cx="37" cy="35" r="9"/>'
    '<circle cx="31" cy="28" r="13"/>'
    '<rect x="19" y="35" width="24" height="9" rx="4.5"/>'
    '</g>'
)

_BACK_CLOUD = (
    '<g fill="currentColor" opacity="0.4">'
    '<circle cx="21" cy="30" r="9"/>'
    '<circle cx="31" cy="27" r="11"/>'
    '<rect x="16" y="31" width="20" height="7" rx="3.5"/>'
    '</g>'
)

_RAIN_LINES = (
    '<g stroke="currentColor" stroke-width="3.4" stroke-linecap="round">'
    '<path d="M23 50l-2.5 8M32 50l-2.5 8M41 50l-2.5 8"/>'
    '</g>'
)

_DRIZZLE_LINES = (
    '<g stroke="currentColor" stroke-width="3" stroke-linecap="round">'
    '<path d="M24 51l-1.6 5M33 51l-1.6 5M42 51l-1.6 5"/>'
    '</g>'
)

# Kept inside the 64-unit box on purpose: an earlier version ran to y=68 and the
# tip was clipped by the viewBox.
_BOLT = '<path d="M36 46l-9 11h6l-2 7 10-10h-6z" fill="currentColor"/>'

_FROST = (
    '<g stroke="currentColor" stroke-width="2.6" stroke-linecap="round">'
    '<path d="M23 52v10M19 54.5l8 5M27 54.5l-8 5"/>'
    '<path d="M41 52v10M37 54.5l8 5M45 54.5l-8 5"/>'
    '</g>'
)

_SNOWFLAKES = (
    '<g stroke="currentColor" stroke-width="2.6" stroke-linecap="round">'
    '<path d="M23 52v10M18.8 54.5l8.4 5M27.2 54.5l-8.4 5"/>'
    '<path d="M41 52v10M36.8 54.5l8.4 5M45.2 54.5l-8.4 5"/>'
    '</g>'
)

_FOG_LINES = (
    '<g stroke="currentColor" stroke-width="3.2" stroke-linecap="round" opacity="0.75">'
    '<path d="M16 50h32M21 57h26"/>'
    '</g>'
)

WEATHER_ICONS = {
    # Clear sky, and mainly clear, are the same picture to a glance across a room.
    '01': _SUN,
    '02': _SUN + _CLOUD,
    '04': _BACK_CLOUD + _CLOUD,
    # Drizzle reads as shorter, lighter strokes than rain.
    '09': _CLOUD + _DRIZZLE_LINES,
    '10': _CLOUD + _RAIN_LINES,
    # Freezing rain and snow share the cloud; sleet strokes read as mixed.
    '13': _CLOUD + _FROST,
    '14': _CLOUD + _SNOWFLAKES,
    # Thunderstorm gets the bolt, which is what you actually want to notice.
    '11': _CLOUD + _BOLT,
    '50': _CLOUD + _FOG_LINES,
}

_FALLBACK = _CLOUD + _RAIN_LINES

_TEMPLATE = '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{}</svg>'


def weather_icon(icon_code):
    """Inline SVG for a WMO icon code assigned in weather.py.

    Falls back to a rain cloud for an unknown code so a new WMO code renders as
    something honest rather than an empty box. Marked safe for Jinja: this is our
    own markup, not user input.
    """
    return _TEMPLATE.format(WEATHER_ICONS.get(icon_code, _FALLBACK))