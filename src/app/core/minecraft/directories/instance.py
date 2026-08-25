from pathlib import Path

from app.core.addon.pack.pack_file import PackFile
from app.core.common import read_model
from app.core.models.version_meta import VersionMeta
from app.third_party.mojang.models import VersionMetaModel as MojangVersionMetaModel
from .base import BaseDirectory


class InstanceDirectory(BaseDirectory):
    __slots__ = [
        'path',
        '_version_meta',
        '_ins_info',
        '_info_file',
        '_name',
        '_mojang_meta_file', '_main_file', '_meta_file'
    ]

    def __init__(self, path):
        self.path = Path(path)

        self._version_meta = None
        self._ins_info = None

        self._name = self.path.name

        self._mojang_meta_file = self.path / (self.path.name + '.json')
        self._meta_file = self.path / (self.path.name + '.mpk')
        self._main_file = self.path / (self.path.name + '.jar')
        # self._info_file = self.path / '.minecraft-version'  # TODO

    @property
    def mojang_version_meta(self) -> MojangVersionMetaModel:
        return read_model(self._mojang_meta_file, MojangVersionMetaModel)

    @property
    def version_meta(self) -> VersionMeta:
        if self._version_meta is None:
            self._version_meta = read_model(self.meta_file, VersionMeta, 'msgpack')

        return self._version_meta

    @property
    def name(self):
        return self._name

    @property
    def meta_file(self):
        return self._meta_file

    @property
    def mojang_meta_file(self):
        return self._mojang_meta_file

    @property
    def main_file(self):
        return self._main_file

    @property
    def info_file(self):
        return self._info_file

    @property
    def natives_dir(self):
        return self.path / (self.name + '-natives')

    @property
    def screenshots_dir(self):
        return self.path / 'screenshots'

    @property
    def logs_dir(self):
        return self.path / 'logs'

    @property
    def resourcepacks_dir(self):
        return self.path / 'resourcepacks'

    @property
    def datapacks_dir(self):
        return self.path / 'datapacks'

    @property
    def shaderpacks_dir(self):
        return self.path / 'shaderpacks'

    @property
    def saves_dir(self):
        return self.path / 'saves'

    @property
    def mods_dir(self):
        return self.path / 'mods'

    def is_valid(self):
        return self.meta_file.exists()

    @property
    def screenshot_files(self):
        return list(self.screenshots_dir.iterdir())

    @property
    def disabled_mod_files(self):
        return [i for i in self.mods_dir.glob('*.jar.disabled') if i.is_file()]

    @property
    def enabled_mod_files(self):
        return [i for i in self.mods_dir.glob('*.jar') if i.is_file()]

    @property
    def all_mod_files(self):
        return self.enabled_mod_files + self.disabled_mod_files

    @property
    def saves_paths(self):
        return [i for i in self.saves_dir.iterdir() if i.is_dir()]

    def _iter_packs(self, dir):
        return (
            PackFile.open(filename)
            for filename in dir.iterdir()
            if filename.is_file()
        )

    def iter_resourcepacks(self):
        return self._iter_packs(self.resourcepacks_dir)

    def iter_shaderpacks(self):
        return self._iter_packs(self.shaderpacks_dir)

    def iter_datapacks(self):
        return self._iter_packs(self.datapacks_dir)
