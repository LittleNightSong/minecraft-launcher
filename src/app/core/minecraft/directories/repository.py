from pathlib import Path

from app.core.minecraft import InstanceDirectory
from app.core.minecraft.directories import AssetsDirectory
from app.core.minecraft.directories.base import BaseDirectory
from app.core.minecraft.directories.launcher import LauncherDataDirectory
from app.core.minecraft.directories import LibrariesDirectory
from app.core.minecraft.directories.versions import VersionsDirectory


class Repository(BaseDirectory):
    __slots__ = ['versions', 'assets', 'libraries', 'launcher_data']
    def __init__(self, path):
        self.path = Path(path)
        self.versions = VersionsDirectory(self.path / 'versions')
        self.assets = AssetsDirectory(self.path / 'assets')
        self.libraries = LibrariesDirectory(self.path / 'libraries')
        self.launcher_data = LauncherDataDirectory(self.path / '.HCL')

    def instance(self, name) -> InstanceDirectory:
        return self.versions.instance(name)

    def iter_instances(self, skip_broken=True):
        return self.versions.instances(skip_broken=skip_broken)

    def librarypath(self, name: str) -> Path:
        return self.libraries.library_path(name)

    def assetpath(self, hash: str) -> Path:
        return self.assets.object(hash).path

    @property
    def file_cacher(self):
        return self.launcher_data.file_cacher

    @property
    def model_cacher(self):
        return self.launcher_data.model_cacher

    def ensure_exists(self):
        super().ensure_exists()
        self.launcher_data.ensure_exists()
        self.assets.ensure_exists()
        self.libraries.ensure_exists()
        self.versions.ensure_exists()
