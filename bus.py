import json
import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

IBUS_URL = 'https://api.tmb.cat/v1/itransit/bus/parades/{stop}'


def load_credentials(path='./credentials/tmb.json'):
    """Read app_id/app_key from a JSON file, allowing env overrides."""
    app_id = os.getenv('TMB_APP_ID')
    app_key = os.getenv('TMB_APP_KEY')

    if app_id and app_key:
        return app_id, app_key

    if not os.path.exists(path):
        raise FileNotFoundError(
            f'TMB credentials not found at {path}. Create it with app_id and app_key, '
            'or set the TMB_APP_ID and TMB_APP_KEY environment variables.'
        )

    with open(path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)

    app_id = app_id or data.get('app_id')
    app_key = app_key or data.get('app_key')
    if not app_id or not app_key:
        raise ValueError(f'{path} must contain both "app_id" and "app_key"')

    return app_id, app_key


class BusService:
    """Live bus departures for a stop via the TMB iBus API."""

    def __init__(self, stop_id, line=None, destination_filter=None,
                 credentials_path='./credentials/tmb.json', timezone='Europe/Madrid',
                 departures_to_show=3, cache_ttl_secs=60, request_timeout=10,
                 expected_stop_name=None):
        self.stop_id = str(stop_id)
        self.line = str(line) if line else None
        self.destination_filter = destination_filter or None
        self.credentials_path = credentials_path
        self.timezone = ZoneInfo(timezone)
        self.departures_to_show = departures_to_show
        self.cache_ttl_secs = cache_ttl_secs
        self.request_timeout = request_timeout
        self.expected_stop_name = expected_stop_name or None

        self._lock = threading.Lock()
        self._cache = None
        self._cache_time = 0.0

    def get_departures(self):
        """Return {'ok': True, 'departures': [...]} or {'ok': False, 'error': str}."""
        with self._lock:
            if self._cache and (time.time() - self._cache_time) < self.cache_ttl_secs:
                return self._cache

            result = self._fetch()
            self._cache = result
            self._cache_time = time.time()
            return result

    def _fail(self, error):
        """Uniform failure shape so the template never has to guess.

        The detailed reason goes to the log; the frame only ever shows the
        short public message. A user fighting the bluetooth speaker next to
        the router does not care that an SSLError wrapped a ConnectionPool.
        """
        logging.error('Bus lookup failed: %s', error)
        return {'ok': False, 'error': "Couldn't fetch bus information from TMB",
                'departures': [], 'notices': []}

    def _fetch(self):
        try:
            app_id, app_key = load_credentials(self.credentials_path)
            response = requests.get(
                IBUS_URL.format(stop=self.stop_id),
                params={'app_id': app_id, 'app_key': app_key},
                timeout=self.request_timeout,
            )
        except FileNotFoundError as e:
            return self._fail(str(e))
        except requests.RequestException as e:
            return self._fail(f'Could not reach the TMB API: {e}')

        if response.status_code in (401, 403):
            return self._fail('TMB rejected the API key (check credentials/tmb.json)')
        if response.status_code == 404:
            return self._fail(f'TMB has no stop {self.stop_id}')
        if response.status_code >= 400:
            return self._fail(f'TMB API returned HTTP {response.status_code}')

        try:
            return self._parse(response.json())
        except (ValueError, KeyError, TypeError) as e:
            logging.exception('Unexpected TMB response shape')
            return self._fail(f'Could not read the TMB response: {e}')

    def _parse(self, payload):
        now = datetime.now(self.timezone)
        server_ms = payload.get('timestamp')
        parades = payload.get('parades') or []
        if not parades:
            # An empty list is the API working, not failing: it is what iBus returns
            # for a stop with no service in the window, so stop 789 looks like this
            # between roughly 00:00 and 06:00. Callers render a quiet empty state.
            logging.info('No parades in the TMB response for stop %s', self.stop_id)
            return {
                'ok': True,
                'stop_name': None,
                'service': False,
                'departures': [],
                'notices': [],
                'fetched_at': now.strftime('%H:%M:%S'),
            }

        stop_name = parades[0].get('nom_parada') or f'Stop {self.stop_id}'

        notices = []
        if self.expected_stop_name and stop_name.casefold() != self.expected_stop_name.casefold():
            message = (f'Stop {self.stop_id} is now called "{stop_name}" in the TMB data '
                       f'(config expects "{self.expected_stop_name}")')
            logging.warning(message)
            notices.append(message)

        trajectories = parades[0].get('linies_trajectes') or []
        if self.line:
            matching = [t for t in trajectories
                        if str(t.get('codi_linia')) == self.line or str(t.get('nom_linia')) == self.line]
            if not matching:
                available = ', '.join(sorted({str(t.get('nom_linia')) for t in trajectories})) or 'none'
                return self._fail(
                    f'Line {self.line} does not serve stop {self.stop_id} (has: {available})')
            trajectories = matching

        # A destination filter is a preference, not a hard requirement: if it matches
        # nothing we would rather show the line than claim there is no service.
        if self.destination_filter:
            needle = self.destination_filter.casefold()
            preferred = [t for t in trajectories
                         if needle in str(t.get('desti_trajecte', '')).casefold()]
            if preferred:
                trajectories = preferred
            else:
                logging.warning(
                    'No trajectory at stop %s matched destination %r; showing all for the line',
                    self.stop_id, self.destination_filter)

        now_ms = int(now.timestamp() * 1000)
        if not server_ms:
            server_ms = now_ms

        departures = []
        for trajectory in trajectories:
            destination = trajectory.get('desti_trajecte') or ''
            line_label = str(trajectory.get('nom_linia') or trajectory.get('codi_linia') or '')
            for bus in trajectory.get('propers_busos') or []:
                arrival_ms = bus.get('temps_arribada')
                if not arrival_ms:
                    continue
                # Keep arrivals still in the future, and anything already underway.
                if arrival_ms < server_ms - 120000:
                    continue

                departures.append({
                    'time': datetime.fromtimestamp(arrival_ms / 1000, self.timezone).strftime('%H:%M'),
                    'minutes': max(0, round((arrival_ms - server_ms) / 60000)),
                    'line': line_label,
                    'destination': destination,
                })

        departures.sort(key=lambda d: d['minutes'])

        return {
            'ok': True,
            'stop_name': stop_name,
            # Tells the template the stop is reachable but has nothing running now, so
            # it can say so quietly instead of implying an error.
            'service': bool(departures),
            'departures': departures[:self.departures_to_show],
            'notices': notices,
            'fetched_at': now.strftime('%H:%M:%S'),
        }