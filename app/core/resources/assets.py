import dataclasses
import os
from os import PathLike
from pathlib import Path, PurePosixPath

from app.core.common import read_model
from app.core.minecraft import AssetIndexModel
from app.core.resources.base import BaseDirectory


class AssetIndexType:
    def __init__(self, fullpath):
        self.fullpath = fullpath

    def __fspath__(self):
        return self.fullpath

    @property
    def content(self) -> AssetIndexModel:
        return read_model(self.fullpath, AssetIndexModel)

    def open(self, mode='rb'):
        return open(self.fullpath, mode)


@dataclasses.dataclass(slots=True)
class AssetObjectType:
    path: str | bytes | PathLike
    vpath: PurePosixPath | None = None
    hash: str | None = None
    size: int | None = None

    def __fspath__(self):
        return os.fspath(self.path)

    def open(self, mode='rb'):
        return open(self.path, mode)


class ObjectsDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def object(self, hash) -> AssetObjectType:
        hash = str(hash)
        return AssetObjectType(self.path / hash[:2] / hash)

    def __getitem__(self, item):
        return self.object(item)


class IndexesDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def exists(self, index_id):
        return self.fullpath(index_id).exists()

    def read(self, index_id):
        return read_model(self.fullpath(index_id), AssetIndexModel)

    def fullpath(self, index_id):
        return self.path / (str(index_id) + '.json')


class AssetsDirectory(BaseDirectory):
    __slots__ = ['objects', 'indexes']

    def __init__(self, path):
        self.path = Path(path)
        self.objects = ObjectsDirectory(self.path / 'objects')
        self.indexes = IndexesDirectory(self.path / 'indexes')

    def ensure_exists(self):
        super().ensure_exists()
        self.objects.ensure_exists()
        self.indexes.ensure_exists()

    def object(self, hash):
        return self.objects.object(hash)

    def index(self, id):
        return self.indexes.fullpath(id)

    def __getitem__(self, item):
        return self.object(item)

    def __call__(self, id):
        return self.index(id)

    def __truediv__(self, other):
        return self.object(other).path
