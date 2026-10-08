import logging
import threading
import time

import requests

GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'

WMO_CODES = {
    0: ('Clear sky', '01'),
    1: ('Mainly clear', '01'),
    2: ('Partly cloudy', '02'),
    3: ('Overcast', '04'),
    45: ('Fog', '50'),
    48: ('Depositing rime fog', '50'),
    51: ('Light drizzle', '09'),
    53: ('Moderate drizzle', '09'),
    55: ('Dense drizzle', '09'),
    56: ('Light freezing drizzle', '13'),
    57: ('Dense freezing drizzle', '13'),
    61: ('Slight rain', '10'),
    63: ('Moderate rain', '10'),
    65: ('Heavy rain', '10'),
    66: ('Light freezing rain', '13'),
    67: ('Heavy freezing rain', '13'),
    71: ('Slight snow fall', '14'),
    73: ('Moderate snow fall', '14'),
    75: ('Heavy snow fall', '14'),
    77: ('Snow grains', '14'),
    80: ('Slight rain showers', '09'),
    81: ('Moderate rain showers', '09'),
    82: ('Violent rain showers', '09'),
    85: ('Slight snow showers', '14'),
    86: ('Heavy snow showers', '14'),
    95: ('Thunderstorm', '11'),
    96: ('Thunderstorm with slight hail', '11'),
    99: ('Thunderstorm with heavy hail', '11'),
}

FALLBACK_FORECAST_URL = 'https://api.openweathermap.org/data/2.5/forecast'


class WeatherService:
    """Fetches a daily forecast, defaulting to Open-Meteo which needs no API key."""

    def __init__(self, location='Barcelona,ES', timezone='Europe/Madrid',
                 api_key=None, units='metric', cache_ttl_secs=600,
                 request_timeout=10, provider='open-meteo'):
        self.location = location
        self.timezone = timezone
        self.api_key = api_key
        self.units = units
        self.cache_ttl_secs = cache_ttl_secs
        self.request_timeout = request_timeout
        self.provider = provider

        self._lock = threading.Lock()
        self._cache = None
        self._cache_time = 0.0
        self._coords = None
        self._error = None

    def get_forecast(self):
        """Return a list of day dicts for today plus the next two days."""
        with self._lock:
            fresh = self._cache_time and (time.time() - self._cache_time) < self.cache_ttl_secs
            if fresh and self._cache:
                return self._cache

            try:
                forecast = self._fetch_forecast()
                self._error = None
            except Exception as e:
                logging.error(f"Weather fetch failed: {e}")
                self._error = str(e)
                forecast = []

            self._cache = forecast
            self._cache_time = time.time()
            return forecast

    @property
    def error(self):
        with self._lock:
            return self._error

    def _fetch_forecast(self):
        if self.provider == 'openweathermap':
            return self._fetch_openweathermap()

        coords = self._get_coords()
        params = {
            'latitude': coords['latitude'],
            'longitude': coords['longitude'],
            'daily': ('weather_code,temperature_2m_max,temperature_2m_min,'
                      'precipitation_probability_max'),
            'forecast_days': 3,
            'timezone': self.timezone,
        }
        response = requests.get(FORECAST_URL, params=params, timeout=self.request_timeout)
        response.raise_for_status()
        daily = response.json().get('daily', {})

        days = []
        for idx, date_str in enumerate(daily.get('time', [])):
            code = daily['weather_code'][idx]
            description, icon = WMO_CODES.get(code, ('Unknown', '02'))
            days.append({
                'date': date_str,
                'temp_min': daily['temperature_2m_min'][idx],
                'temp_max': daily['temperature_2m_max'][idx],
                'precipitation_probability': daily.get('precipitation_probability_max', [None] * len(daily['time']))[idx],
                'description': description,
                'icon': icon,
                'weather_code': code,
            })
        return days[:3]

    def _fetch_openweathermap(self):
        if not self.api_key:
            raise RuntimeError('weather_api_key is required for the openweathermap provider')

        response = requests.get(FALLBACK_FORECAST_URL, params={
            'q': self.location,
            'appid': self.api_key,
            'units': self.units,
        }, timeout=self.request_timeout)
        response.raise_for_status()

        buckets = {}
        for item in response.json().get('list', []):
            date_str = item['dt_txt'].split(' ')[0]
            bucket = buckets.setdefault(date_str, {
                'date': date_str,
                'temp_min': item['main']['temp_min'],
                'temp_max': item['main']['temp_max'],
                'precipitation_probability': None,
                'description': item['weather'][0]['description'].capitalize(),
                'icon': item['weather'][0]['icon'][:2],
                'weather_code': None,
            })
            bucket['temp_min'] = min(bucket['temp_min'], item['main']['temp_min'])
            bucket['temp_max'] = max(bucket['temp_max'], item['main']['temp_max'])

        return sorted(buckets.values(), key=lambda d: d['date'])[:3]

    def _get_coords(self):
        if self._coords:
            return self._coords

        response = requests.get(GEOCODE_URL, params={'name': self._geocode_query(), 'count': 1},
                                timeout=self.request_timeout)
        response.raise_for_status()
        results = response.json().get('results')
        if not results:
            raise RuntimeError(f'Could not geocode location "{self.location}"')

        self._coords = {
            'latitude': results[0]['latitude'],
            'longitude': results[0]['longitude'],
        }
        return self._coords

    def _geocode_query(self):
        """Open-Meteo geocoding wants a bare place name, so drop any ",CC" suffix."""
        return self.location.split(',')[0].strip()
