"""Long-lived service objects, rebuilt when config.yaml changes on disk.

Services used to be constructed once at import time, which meant editing e.g.
bus_stop_id appeared to have no effect until a restart. They are rebuilt here
whenever the config file's mtime changes, so the whole app honours live edits.
"""

import logging
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bus import BusService
from icons import weather_icon
from photos import PhotoService
from weather import WeatherService


class Services:
    def __init__(self, config):
        self._config = config
        self._built_for = object()
        self._lock = threading.RLock()
        self._weather = None
        self._buses = []
        self._photos = None
        self._timezone = ZoneInfo('UTC')

    def _ensure(self):
        version = self._config.version
        if version == self._built_for and self._weather is not None:
            return
        with self._lock:
            if version == self._built_for and self._weather is not None:
                return
            self._build()
            self._built_for = version

    def _build(self):
        c = self._config
        timezone = c.get('clock_timezone', 'Europe/Madrid')
        self._timezone = ZoneInfo(timezone)
        self._weather = WeatherService(
            location=c.get('weather_location', 'Barcelona,ES'),
            timezone=timezone,
            api_key=c.get('weather_api_key'),
            units=c.get('weather_units', 'metric'),
            cache_ttl_secs=c.get('weather_cache_ttl_secs', 600),
            provider=c.get('weather_provider', 'open-meteo'),
        )
        self._buses = [BusService(
            stop_id=stop.get('stop_id'),
            line=stop.get('line'),
            destination_filter=stop.get('destination_filter'),
            credentials_path=c.get('bus_credentials_path', './credentials/tmb.json'),
            timezone=timezone,
            departures_to_show=c.get('bus_departures_to_show', 3),
            cache_ttl_secs=c.get('bus_poll_interval_secs', 60),
            expected_stop_name=stop.get('expected_stop_name'),
        ) for stop in (c.get('bus_stops') or [])]
        # Retire the previous photo thread so a config edit cannot leave two running.
        if self._photos is not None:
            self._photos.stop()
        self._photos = PhotoService(c)
        self._photos.start()
        logging.info('Services built (timezone=%s)', timezone)

    @property
    def weather(self):
        self._ensure()
        return self._weather

    @property
    def buses(self):
        """One BusService per configured stop, in config order."""
        self._ensure()
        return self._buses

    @property
    def photos(self):
        self._ensure()
        return self._photos

    @property
    def timezone(self):
        self._ensure()
        return self._timezone

    def now(self):
        return datetime.now(self.timezone)

    def clock_synced(self):
        """True once NTP has corrected the clock since boot.

        The Pi has no RTC, so a fresh boot shows a guessed time until
        timesyncd does its first sync. timesyncd drops an empty marker file
        once it has synchronized; its absence is the honest signal that the
        frame's clock is wrong and the bus minutes next to it are too. A cheap
        stat on the request path, no network. On a dev laptop there is no
        timesyncd marker and the machine has its own battery-backed clock, so
        treat it as synced.
        """
        import os
        marker = '/run/systemd/timesync/synchronized'
        if os.path.isdir(os.path.dirname(marker)):
            return os.path.exists(marker)
        return True

    def wifi_online(self):
        """True when wlan0 has a carrier, read from sysfs (no network I/O).

        The frame is wifi-only, so if the link is down the bus minutes are
        stale and an unsynced clock cannot be corrected. This is deliberately
        a local file read: probing reachability would block a request thread
        and made no sense when the point is just to warn that the link is down.
        A non-Pi machine has no wlan0; assume it is fine.
        """
        import os
        state_file = '/sys/class/net/wlan0/operstate'
        try:
            with open(state_file) as f:
                return f.read().strip() == 'up'
        except OSError:
            return True

    def weather_forecast(self):
        """Forecast days shaped for display, honouring forecast_days/show_precipitation."""
        forecast_days = int(self._config.get('forecast_days', 3))
        show_precipitation = bool(self._config.get('show_precipitation', True))
        today = self.now().date()

        days = []
        raw = self.weather.get_forecast()[:forecast_days]
        for idx, day in enumerate(raw):
            try:
                day_date = date.fromisoformat(day['date'])
            except (TypeError, ValueError):
                day_date = today + timedelta(days=idx)

            delta = (day_date - today).days
            if delta <= 0:
                label = 'Today'
            elif delta == 1:
                label = 'Tomorrow'
            else:
                label = day_date.strftime('%a')

            days.append({
                'label': label,
                'date_label': day_date.strftime('%d %b'),
                'temp_min': round(day['temp_min']),
                'temp_max': round(day['temp_max']),
                'description': day['description'],
                'icon': day['icon'],
                # Pre-rendered here so the template only has to interpolate markup.
                'icon_svg': weather_icon(day['icon']),
                'precipitation_probability': day.get('precipitation_probability'),
                'show_precipitation': show_precipitation,
            })
        return days

    def bus_departures(self):
        """One result per configured stop: [{'label', 'result'}], or None if disabled."""
        if not self._config.get('enable_bus', True):
            return None
        stops = self._config.get('bus_stops') or []
        return [{'label': stop.get('label', ''), 'result': service.get_departures()}
                for stop, service in zip(stops, self.buses)]