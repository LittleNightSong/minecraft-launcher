from pathlib import Path

from app.resources.assets import AssetsDirectory
from app.resources.base import BaseDirectory
from app.resources.launcher import LauncherDataDirectory
from app.resources.libraries import LibrariesDirectory
from app.resources.versions import VersionsDirectory


class Repository(BaseDirectory):
    __slots__ = ['versions', 'assets', 'libraries', 'launcher_data']
    def __init__(self, path):
        self.path = Path(path)
        self.versions = VersionsDirectory(self.path / 'versions')
        self.assets = AssetsDirectory(self.path / 'assets')
        self.libraries = LibrariesDirectory(self.path / 'libraries')
        self.launcher_data = LauncherDataDirectory(self.path / '.HCL')

    def ensure_exists(self):
        super().ensure_exists()
        self.launcher_data.ensure_exists()
        self.assets.ensure_exists()
        self.libraries.ensure_exists()
