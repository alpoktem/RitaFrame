import os

import yaml


class ConfigLoader:
    """Reads config.yaml, reloading it automatically when the file changes.

    Exposes `version` (the file mtime) so long-lived objects can tell whether the
    settings they were built from are still current.
    """

    def __init__(self, config_path='config.yaml'):
        self.config_path = config_path
        self._config = {}
        self._mtime = None
        self.reload()

    def reload(self):
        self._config = self._read()
        self._mtime = self._stat()
        return self._config

    def _read(self):
        if not os.path.exists(self.config_path):
            return {}
        with open(self.config_path, 'r', encoding='utf-8') as handle:
            return yaml.safe_load(handle) or {}

    def _stat(self):
        try:
            return os.path.getmtime(self.config_path)
        except OSError:
            return None

    def _refresh(self):
        if self._stat() != self._mtime:
            self.reload()
        return self._config

    @property
    def config(self):
        return self._refresh()

    @property
    def version(self):
        self._refresh()
        return self._mtime

    def get(self, key, default=None):
        return self._refresh().get(key, default)