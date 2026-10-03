"""Google Photos support.

Dormant unless `enable_photos` is true, and safe to enable at any time:

* The OAuth flow opens a browser and blocks until it completes, so it must never
  run while a page is rendering. All network and auth work happens on a background
  thread; the request path only ever reads an already-resolved URL.
* If auth has not been completed yet the frame renders normally with no photo
  rather than hanging. Use /photos/auth to do the one-off browser login.
* photosapi is imported lazily, so google-* stays an optional dependency.
"""

import logging
import threading
import time

# Status values surfaced in /api/status.
DISABLED = 'disabled'
PENDING = 'pending_auth'
READY = 'ready'
ERROR = 'error'


class PhotoService:
    def __init__(self, config):
        self._config = config
        self._api = None
        self._items = []
        self._index = 0
        self._current_url = None
        self._status = DISABLED
        self._error = None
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

    # ---- configuration -------------------------------------------------

    @property
    def enabled(self):
        return bool(self._config.get('enable_photos', False))

    @property
    def mode(self):
        """Either 'background' (photo behind the active view) or 'carousel'."""
        return self._config.get('photos_mode', 'background')

    @property
    def status(self):
        return self._status

    @property
    def error(self):
        return self._error

    def _set_state(self, status, error=None):
        with self._lock:
            if status != self._status:
                logging.info('Photos: %s -> %s%s', self._status, status,
                             f' ({error})' if error else '')
            self._status = status
            self._error = error

    # ---- lifecycle -----------------------------------------------------

    def start(self):
        """Kick off the refresher thread if photos are enabled. Cheap and non-blocking."""
        if not self.enabled:
            self._set_state(DISABLED)
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                self._refresh()
            except Exception as e:  # never let the thread die silently
                self._set_state(ERROR, str(e))
                logging.error('Photos refresh failed: %s', e)
            # Short first interval so a just-authenticated frame picks up a photo
            # quickly, then back off to the configured rotation.
            self._stop.wait(30 if self._status != READY else self._rotation_secs())

    def _rotation_secs(self):
        return max(30, int(self._config.get('photos_rotation_secs', 3600)))

    def _refresh(self):
        # Never open a browser from the refresh thread: on a headless frame nobody
        # would ever complete it. Auth is an explicit step via /photos/auth.
        secret_path = self._config.get('client_secret_path')
        from photosapi import GooglePhotosApi
        if not GooglePhotosApi.has_stored_credentials(secret_path):
            self._set_state(PENDING,
                            'Photos enabled but not authenticated yet - open /photos/auth once')
            return

        api = self._get_api()
        album = self._config.get('album_name', 'RitaFrame')
        album_dict = api.get_album_dict(album)
        items = (album_dict or {}).get('items') or []
        if not items:
            self._set_state(ERROR, f'Album "{album}" has no items')
            return

        urls = [u for u in (self._with_resolution(i) for i in items) if u]
        if not urls:
            self._set_state(ERROR, 'Album contained no usable photo URLs')
            return

        with self._lock:
            previous = self._current_url
            self._items = urls
            self._index = urls.index(previous) + 1 if previous in urls else 0
            self._index %= len(urls)
            self._current_url = urls[self._index]
            self._index = (self._index + 1) % len(urls)
        self._set_state(READY)

    def _get_api(self):
        if self._api is None:
            from photosapi import GooglePhotosApi
            self._api = GooglePhotosApi(
                client_secret_file=self._config.get('client_secret_path'))
            logging.info('Google Photos API initialised')
        return self._api

    def _with_resolution(self, item):
        url = item.get('baseUrl')
        if not url:
            return None
        long_edge = str(self._config.get('frame_long_edge', '800'))
        short_edge = str(self._config.get('frame_short_edge', '480'))
        try:
            horizontal = int(item['width']) > int(item['height'])
        except (KeyError, TypeError, ValueError):
            horizontal = True
        if horizontal:
            return f'{url}=w{long_edge}-h{short_edge}'
        return f'{url}=h{long_edge}-w{short_edge}'

    # ---- request path (must never block or perform I/O) ----------------

    def current_url(self):
        with self._lock:
            return self._current_url

    def background_url(self):
        if not self.enabled or self.mode != 'background':
            return None
        return self.current_url()

    def next_url(self):
        if not self.enabled:
            return None
        return self.current_url()

    # ---- explicit, user-initiated authentication ------------------------

    def authenticate(self):
        """Run the OAuth flow deliberately. Blocks on purpose: this is the setup step."""
        if not self.enabled:
            return {'ok': False, 'error': 'Photos are disabled (enable_photos: false)'}
        try:
            self._get_api()
            self._refresh()
        except Exception as e:
            self._set_state(ERROR, str(e))
            return {'ok': False, 'error': str(e)}
        return {'ok': self._status == READY, 'status': self._status, 'error': self._error}