
# RitaFrame

A dashboard for a home screen: clock, weather, and the bus timetable for the school run.

Originally built as a cloud-based photo frame for a Raspberry Pi, pulling images from a
Google Photos album with optional PIR motion detection. That carousel still exists but is
now off by default, so you can run the dashboard on its own.

## Running it

```bash
pip3 install -r requirements.txt
python3 app.py
```

Then open [localhost:8000](http://localhost:8000).

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
```

`app.py` only wires things together — data fetching lives in the service modules and markup
lives in `views.py`, so adding a view never means touching the routes or the app setup.

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
| Motion | `run_motion_detection`, `pir_pin`, `sleep_on_secs` |

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

Off by default. `motionio.py` imports `RPi.GPIO` lazily, so the app runs fine on a
non-Pi machine with `run_motion_detection: false`.

## Hardware Setup (Raspberry Pi photo frame mode)

- Raspberry Pi (any model with network connectivity)
- MicroSD card (8 GB or more recommended) with Raspberry Pi OS
- Power supply for the Raspberry Pi
- HDMI-compatible display monitor
- PIR motion sensor
- Jumper wires (for connecting the PIR sensor to the Raspberry Pi)

### PIR motion sensor setup

PIR sensors come with three pins: GND, OUT and VIN. Use the jumper wires to connect GND to a ground pin (e.g. 6), VIN to a power pin (e.g. 2) and OUT to a GPIO pin (e.g. 11, which is GPIO 17). For further information on GPIO pins [check here](https://randomnerdtutorials.com/raspberry-pi-pinout-gpios/).

## Autostart Setup

To have the app start automatically on boot, copy the `autostart` file to `~/.config/lxsession/LXDE-pi`:

```bash
sudo cp etc/lxboot/chromium/autostart ~/.config/lxsession/LXDE-pi
```

## Raspberry Pi Zero setup

Chromium is too heavy for a Zero. Install [surf](https://surf.suckless.org/) instead:

```bash
sudo apt-get update
sudo apt-get install surf
```

Surf has no kiosk mode, so the scripts under `etc/surf` boot it once the web app is
ready and then put it full screen:

```bash
sudo cp etc/lxboot/surf/autostart ~/.config/lxsession/LXDE-pi/autostart
```

## References
I got inspired and built on top of the work below:

- [samuelclay/Raspberry-Pi-Photo-Frame](https://github.com/samuelclay/Raspberry-Pi-Photo-Frame)
- [polzerdo55862/google-photos-api](https://github.com/polzerdo55862/google-photos-api)
- [Google Photos Library API](https://developers.google.com/photos/library/reference/rest)

## If you like this project

<a href="https://www.buymeacoffee.com/alpoktem" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="60" width="220"></a>
