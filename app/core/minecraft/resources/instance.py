from pathlib import Path

from app.core.common import read_model, write_model
from ..model_version_meta import VersionMetaModel
from .base import BaseDirectory


class InstanceDirectory(BaseDirectory):
    __slots__ = [
        'path',
        '_version_meta', '_ins_info',
        '_name', '_meta_file', '_main_file', '_info_file'
    ]

    def __init__(self, path):
        self.path = Path(path)

        self._version_meta = None
        self._ins_info = None

        self._name = self.path.name

        self._meta_file = self.path / (self.path.name + '.json')
        self._main_file = self.path / (self.path.name + '.jar')
        # self._info_file = self.path / '.minecraft-version'  # TODO

    @property
    def version_meta(self) -> VersionMetaModel:
        if self._version_meta is None:
            self._version_meta = read_model(self.meta_file, VersionMetaModel)

        return self._version_meta

    @version_meta.setter
    def version_meta(self, value):
        self._version_meta = value
        write_model(self.meta_file, value)

    @property
    def name(self):
        return self._name

    @property
    def meta_file(self):
        return self._meta_file

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
    def shaderpacks_dir(self):
        return self.path / 'shaderpacks'

    @property
    def saves_dir(self):
        return self.path / 'saves'

    @property
    def mods_dir(self):
        return self.path / 'mods'

    def is_valid(self):
        return (self.path / (self.path.name + '.json')).exists()

    @property
    def screenshots(self):
        return list(self.screenshots_dir.iterdir())

    @property
    def disabled_mods(self):
        return [i for i in self.mods_dir.glob('*.jar.disabled') if i.is_file()]

    @property
    def enabled_mods(self):
        return [i for i in self.mods_dir.glob('*.jar') if i.is_file()]

    @property
    def all_mods(self):
        return self.enabled_mods + self.disabled_mods

    @property
    def saves(self):
        return [i for i in self.saves_dir.iterdir() if i.is_dir()]
