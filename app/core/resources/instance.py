from pathlib import Path

import msgspec

from app.core.common import read_model, write_model
from app.core.minecraft import VersionMetaModel
from app.core.resources.base import BaseDirectory


class InstanceInfo(msgspec.Struct, kw_only=True):
    name: str
    mc_version: str

    # loader: str  # TODO: Mod Loader Support
    # loader_version: str


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
        self._info_file = self.path / (self.path.name + '.insmeta.json')

    @property
    def version_meta(self):
        if self._version_meta is None:
            self._version_meta = read_model(self.meta_file, VersionMetaModel)

        return self._version_meta

    @version_meta.setter
    def version_meta(self, value):
        self._version_meta = value
        write_model(self.meta_file, value)

    @property
    def ins_info(self):
        if self._ins_info is None:
            self._ins_info = read_model(self.info_file, InstanceInfo)

        return self._ins_info

    @ins_info.setter
    def ins_info(self, value):
        self._ins_info = value
        write_model(self.info_file, value)

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

    def is_vaild(self):
        return (self.path / (self.path.name + '.json')).exists()
