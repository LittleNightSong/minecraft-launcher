from pathlib import Path

from app.core.minecraft.resources.base import BaseDirectory
from app.core.cacher.model_cacher import CacheManager


class LauncherDataDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)
        self.cacher = CacheManager(self.path / 'cache')

    def ensure_exists(self):
        super().ensure_exists()
        self.cacher.ensure_exists()
