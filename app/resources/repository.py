from pathlib import Path

from app.resources.assets import AssetsDirectory
from app.resources.launcher import LauncherDataDirectory
from app.resources.libraries import LibrariesDirectory
from app.resources.versions import VersionsDirectory


class Repository:
    def __init__(self, path):
        self.path = Path(path)

    @property
    def versions(self):
        return VersionsDirectory(self.path / "versions")

    @property
    def assets(self):
        return AssetsDirectory(self.path / "assets")

    @property
    def launcher_data(self):
        return LauncherDataDirectory(self.path / '.HCL')

    @property
    def libraries(self):
        return LibrariesDirectory(self.path / "libraries")