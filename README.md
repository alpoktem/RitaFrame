
# RitaFrame

A dashboard for a home screen: clock, weather, and the bus timetable for the school run.

It runs on a Raspberry Pi Zero as a kiosk — LXDE boots straight into a fullscreen browser
pointed at a local Flask app, with no desktop or panel in the way. A Google Photos carousel
also exists but is off by default, so the dashboard runs entirely on its own.

The screen is **800x480 landscape** and the app takes roughly **70 seconds from power-on to
serving** on the Pi, so anything that waits for it needs a generous timeout.

## Running it

```bash
pip3 install -r requirements.txt
python3 app.py
```

Then open [localhost:8000](http://localhost:8000).

Google Photos support is optional and lazy; if you turn it on, also install
`pip3 install -r requirements-photos.txt`.

`config.yaml` is reloaded automatically when you edit it — services are rebuilt to match,
so changes take effect on the next page load with no restart.

## Views

The layout shown at `/` is chosen by the `view` key in `config.yaml`:

```yaml
view: clock      # or: photos
```

A view is a `view(config, services) -> str` function returning rendered HTML, registered in
the `VIEWS` dict in `views.py`. To add one, write the function, add it to `VIEWS`, and drop
the matching template in `templates/`.

Every registered view is also served directly at `/view/<name>`, so you can compare layouts
side by side without editing config.

Built-in views:

| View | Description |
| --- | --- |
| `clock` | Clock, three-day forecast, live bus departures |
| `photos` | Full-screen photo carousel |

## Project layout

```
app.py             Flask app factory + routes
config.yaml        all runtime settings (reloaded live)
config_loader.py   reads config.yaml, exposes an mtime "version"
services.py        owns the weather/bus/photo services, rebuilds them on config change
views.py           view registry; renders templates/*.html
bus.py             TMB iBus client
weather.py         Open-Meteo / OpenWeatherMap client
photos.py          Google Photos (lazy, background thread)
photosapi.py       Google Photos API wrapper + OAuth token handling
motionio.py        PIR motion detection (lazy RPi.GPIO import)
templates/         clock.html, photos.html
etc/rotate-display.sh      forces landscape, optional ROTATION= flip
etc/surf/runsurf.sh        waits for the server, opens the browser
etc/surf/surffull.sh       fullscreen + clears the window stacking
etc/lxboot/surf/autostart  LXDE session autostart (surf variant)
etc/lxboot/chromium/autostart  LXDE session autostart (chromium variant)
etc/ritaframe-display.desktop  XDG autostart entry for the rotation
```

`app.py` only wires things together — data fetching lives in the service modules and markup
lives in `views.py`, so adding a view never means touching the routes or the app setup.

`templates/*.html` currently hold their own CSS and JS inline, which keeps each view readable
in one file. That is worth splitting into `static/` once the design work starts.

If you are an AI agent picking this up, read [`AGENTS.md`](AGENTS.md) first — it records the
Pi-specific traps that are expensive to rediscover.

## Running on the Raspberry Pi

The kiosk boots into LXDE, which runs the app and the browser from
`~/.config/lxsession/LXDE-pi/autostart`:

```
point-rpi
@lxterminal -e /bin/bash /home/pi/Documents/RitaFrame/run.sh
@/home/pi/Documents/RitaFrame/etc/surf/runsurf.sh
@/home/pi/Documents/RitaFrame/etc/surf/surffull.sh
```

plus `~/.config/autostart/ritaframe-display.desktop`, which calls
`etc/rotate-display.sh`. The scripts and that autostart file are all in this repo,
so the Pi setup is reproducible rather than hand-edited.

Four things there are load-bearing, each of which broke the frame in practice:

- **The screen boots portrait.** The Pi's HDMI output comes up rotated 90 degrees
  (480x800) even though the panel is physically landscape. `rotate-display.sh`
  picks a landscape mode and sets `--rotate normal`, and `runsurf.sh` calls it
  again before opening the browser so ordering cannot matter.
- **`run.sh` checks its dependencies first.** A missing module used to make the app
  exit silently while the browser sat on "Connection refused". It now names the
  module and the install command, and holds the terminal open.
- **`runsurf.sh` waits for the server to answer** rather than sleeping a fixed 10s,
  and waits for the landscape mode first. `surf` never retries, so launching early
  leaves the frame stuck on a connection error for the whole session.
- **Fullscreen needs the window stacking cleared too.** Three separate bugs here:
  `xdotool key --window` sends a *synthetic* event that surf ignores, so the key has
  to go through XTEST to the activated window; F11 is a *toggle*, so firing it
  blindly un-fullscreens an already-fullscreen window; and surf briefly has only a
  10x10 helper window, so `surffull.sh` waits for a realistically sized one instead
  of grabbing the largest. Finally, LXDE's panel and desktop stack *above* surf and
  re-map themselves after login, so they are disabled in the autostart file rather
  than hidden by script.

Both waits default to 300s because the Pi can take ~70s from boot to serving; the
original 90s budget expired just before the browser appeared.

Cleanup in `surffull.sh` only runs *after* the browser is confirmed fullscreen. If
the app fails to start there is no browser, so the `run.sh` terminal stays on screen
showing the error — which is what you want to see.

Logs land in two places: `~/ritaframe.log` (stdout, via `tee`) and `logs/app.log`
(rotating). Both get the app's own messages, so you can watch for motion events over
SSH:

```bash
tail -f ~/ritaframe.log | grep -i motion
```

After pulling new code on the Pi:

```bash
cd ~/Documents/RitaFrame
python3 -m pip install --user -r requirements.txt
./run.sh
```

To have the app come back by itself if it ever dies, run it under a supervisor rather
than bare `python3 app.py`.

## Configuration

Everything lives in `config.yaml`, grouped by feature:

| Section | Keys |
| --- | --- |
| View | `view` |
| Server | `host`, `port` |
| Appearance | `background_color`, `text_color`, `muted_text_color` |
| Clock | `enable_clock`, `clock_timezone`, `clock_format`, `date_format` (strftime) |
| Weather | `enable_weather`, `weather_provider`, `weather_location`, `forecast_days`, `weather_cache_ttl_secs`, `show_precipitation` |
| Bus | `enable_bus`, `bus_stop_id`, `bus_line`, `bus_destination_filter`, `bus_expected_stop_name`, `bus_poll_interval_secs`, `bus_departures_to_show` |
| Photos | `enable_photos`, `photos_mode`, `photos_rotation_secs`, `photos_overlay_opacity`, `album_name` |
| Motion | `run_motion_detection`, `pir_pin` (BCM), `sleep_on_secs` |

### Endpoints

| Route | Purpose |
| --- | --- |
| `/` | The active view |
| `/view/<name>` | A specific view |
| `/api/status` | Active view, feature flags, service health — handy for a headless frame |
| `/api/clock`, `/api/weather`, `/api/bus` | Individual data feeds |
| `/api/photos/next` | Current photo URL |
| `/photos/auth` | One-off Google Photos OAuth login |

### Weather

Defaults to [Open-Meteo](https://open-meteo.com), which needs **no API key**. Set
`weather_location` to anything geocodable (e.g. `"Barcelona,ES"`) and `forecast_days`
controls how many days ahead to show. To use OpenWeatherMap instead, set
`weather_provider: "openweathermap"` and fill in `weather_api_key`.

Responses are cached for `weather_cache_ttl_secs` so the app isn't hammering the API.

### Bus timetable

Live departures for line **55** toward Parc de Montjuïc, from stop **789**
(Pg de l'Exposició - Santa Madrona), using the [TMB iBus API](https://developer.tmb.cat/).

Get credentials from [developer.tmb.cat](https://developer.tmb.cat/account/applications) —
create an application and you'll get an `app_id` and `app_key`. Save them to
`credentials/tmb.json` (gitignored):

```json
{ "app_id": "...", "app_key": "..." }
```

`TMB_APP_ID` / `TMB_APP_KEY` environment variables override the file if you prefer.

Notes on the data:

- The page reloads on `bus_poll_interval_secs` (60s) because arrival predictions go stale fast.
- The endpoint returns **every** line serving the stop, so `bus_line` is what keeps unrelated
  buses off the frame. `bus_destination_filter` narrows to one direction but is only a
  preference — if it stops matching, the line is still shown rather than claiming no service.
- `bus_expected_stop_name` is compared against the live name from TMB. If they diverge, the
  frame shows a warning. This is the signal that a stop has been renamed or relocated and the
  stop code needs updating.
- iBus v1 documents a single method (arrivals for a stop) and returns only `codi_parada`,
  `nom_parada`, the line/trajectory fields, and `propers_busos[].temps_arribada`/`id_bus`.
  There is no service-alerts method, so stop-change notices have to come from the name check
  above. Arrival times are predictions from the bus's last known position, accurate to about
  a minute.
- Failures render as a visible error rather than a stale or fabricated time.

### Photos (optional, off by default)

Google Photos support is dormant until you set `enable_photos: true`. It is designed to be
safe to enable at any time:

- Nothing Google-related is imported or contacted at startup, so a missing credential file,
  revoked OAuth client, or absent `google-*` package cannot stop the app from running.
- The OAuth flow opens a browser and blocks until completed, so it never runs while a page is
  rendering. All photo work happens on a background thread; the request path only reads an
  already-resolved URL. Before authenticating, `status` reports `pending_auth` and pages
  render normally without a photo.
- To connect, enable photos, then open `/photos/auth` **once** in a browser and complete the
  Google login. A token is cached in `credentials/`.
- `photos_mode: background` renders the photo behind whichever view is active, with
  `photos_overlay_opacity` dimming it for legibility. `photos_mode: carousel` uses the
  full-screen `photos` view instead.
- `photos_rotation_secs` controls how often a new photo is chosen.

### Motion detection (Raspberry Pi)

Controlled by `run_motion_detection` (BCM pin in `pir_pin`, currently 15 = physical
header pin 10). The screen sleeps after `sleep_on_secs` with no detected motion and wakes
on the next detection.

Wiring, as built:

| Signal | Header pin | Note |
| --- | --- | --- |
| `Vin` | 17 | 3.3V, not pin 2's 5V — see below |
| `GND` | 6 | |
| `OUT` | 10 | GPIO15 |

The AM312 is rated DC 2.7-12V, so it runs happily from the 3.3V rail. That matters
because the module's output is driven from `Vin`, and **no Pi GPIO is 5V tolerant**:
powering it from pin 2 would put 5V on a 3.3V pin. Its datasheet states no output high
level, so supplying the lowest in-spec voltage is the safe choice.

Because `config.yaml` is reloaded live, changing `run_motion_detection`, `pir_pin` or
`sleep_on_secs` takes effect without a restart — `MotionController.sync()` reconciles the
detector thread on each request, restarting it when the pin or timeout differs.
`/api/status` reports `motion_detection` (configured) and `motion_running` (thread
actually alive) separately, so a detector that failed to start is visible rather than
looking healthy.

Waking is debounced over two consecutive HIGH samples. The sensor's 2-second blocking
time means it emits some very short spikes, which a single-sample check would treat as
motion.

`motionio.py` imports `RPi.GPIO` lazily, so the app still runs on a non-Pi machine, where
it logs `Motion detection unavailable` and carries on.

## Hardware

- Raspberry Pi Zero (surf is used because Chromium is too heavy for it)
- MicroSD card, 8 GB or more
- HDMI display, **800x480 landscape** (the panel is physically landscape; see rotation below)
- Optional PIR motion sensor on GPIO 17 (physical pin 11)
- Jumper wires

### Screen rotation

The Pi's HDMI output boots **rotated 90 degrees (480x800 portrait)** even though the panel is
physically landscape, so everything starts sideways. `etc/rotate-display.sh` corrects this on
every boot and picks the landscape mode automatically.

To flip the frame upside down — for example so the cable input ends up at the bottom — set
`ROTATION=inverted`:

```bash
ROTATION=inverted ~/Documents/RitaFrame/etc/rotate-display.sh
```

To make that stick across reboots, edit `ROTATION=` near the top of
`etc/rotate-display.sh`. Valid values are the `xrandr` rotations: `normal`, `left`, `right`,
`inverted`. Confirm the result with `xrandr | head -2` — you want to see `800x480` and the
rotation you chose.

### PIR motion sensor

Off by default (`run_motion_detection: false`). `motionio.py` imports `RPi.GPIO` lazily, so
the app runs fine without it.

PIR sensors have three pins: GND, OUT and VIN. Connect GND to a ground pin (e.g. 6), VIN to a
power pin (e.g. 2) and OUT to a GPIO pin (e.g. 11, which is GPIO 17). See the
[GPIO pinout](https://randomnerdtutorials.com/raspberry-pi-pinout-gpios/).

### Light sensor

**Not implemented.** `motionio.py` does control the screen — it sleeps and wakes the display
with `xset dpms` — but it is driven purely by the PIR motion sensor. Nothing anywhere reads
ambient light, and no light-sensor driver exists.

So if a light sensor is wired up, it is currently doing nothing. Treat the hardware as
unverified: the part type and the wiring are both unknown, and an I2C scan of the Pi's bus
found no device responding, so nothing is currently detected on I2C. Establish what part is
fitted and how it is wired before writing any driver code. Likely goal is dimming the screen
at night. See the planned work below.

## Planned work

Rough order of intent, not yet started:

- **Flip the frame 180°** so the cable input sits at the bottom. Set `ROTATION=inverted` as
  described above.
- **Investigate the light sensor.** Nothing reads it today, so first establish what part is
  fitted and how it is wired (I2C vs GPIO vs analog), then decide whether it should dim the
  screen at night.
- **New visual design**, developed on a laptop first rather than on the Pi. It involves images
  and animation, so it wants fast iteration and a real browser; the Pi is only the deployment
  target. Plan for the animation to respect the frame's 800x480 landscape and to avoid
  anything that would tax a Zero.

## Autostart setup

Copy the autostart file into the LXDE session directory:

```bash
sudo cp etc/lxboot/surf/autostart ~/.config/lxsession/LXDE-pi/autostart
```

For the screen rotation to survive reboots, also install the desktop entry:

```bash
mkdir -p ~/.config/autostart
cp etc/ritaframe-display.desktop ~/.config/autostart/
```

Surf is used because Chromium is too heavy for a Zero:

```bash
sudo apt-get update
sudo apt-get install surf
```

## References
I got inspired and built on top of the work below:

- [samuelclay/Raspberry-Pi-Photo-Frame](https://github.com/samuelclay/Raspberry-Pi-Photo-Frame)
- [polzerdo55862/google-photos-api](https://github.com/polzerdo55862/google-photos-api)
- [Google Photos Library API](https://developers.google.com/photos/library/reference/rest)

## If you like this project

<a href="https://www.buymeacoffee.com/alpoktem" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="60" width="220"></a>
