from pathlib import Path

from app.core.resources.base import BaseDirectory
from app.core.resources.cache import CacheManager


class LauncherDataDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)
        self.cache = CacheManager(self.path / 'cache')

    def ensure_exists(self):
        super().ensure_exists()
        self.cache.ensure_exists()
