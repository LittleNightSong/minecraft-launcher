from pathlib import Path

from app.core.cacher.file_cache import FileCacher
from app.core.minecraft.directories.base import BaseDirectory
from app.core.cacher.model_cacher import ModelCacher


class LauncherDataDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)
        self.model_cacher = ModelCacher(self.path / 'cache')
        self.file_cacher = FileCacher(self.path / 'files')

    def ensure_exists(self):
        super().ensure_exists()
        self.model_cacher.ensure_exists()
        self.file_cacher.ensure_exists()
