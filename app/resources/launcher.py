from pathlib import Path

from app.resources.base import BaseDirectory
from app.resources.cache import CacheDirectory


class LauncherDataDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)
        self.cache = CacheDirectory(self.path / 'cache')

    def ensure_exists(self):
        super().ensure_exists()
        self.cache.ensure_exists()
