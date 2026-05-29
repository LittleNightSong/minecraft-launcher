import asyncio
from asyncio import TaskGroup
from pathlib import Path
from typing import Iterable

from app.common import compute_hash
from app.common.methods import read_json
from app.resources.base import BaseDirectory


class ObjectsDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def asset(self, hash) -> Path:
        hash = str(hash)
        return self.path / hash[:2] / hash

    def open(self, hash, mode='rb'):
        path = self.asset(hash)
        path.parent.mkdir(exist_ok=True)
        return open(path, mode)

class IndexesDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def exists(self, index_id):
        return self.fullpath(index_id).exists()

    def read(self, index_id):
        return read_json(self.fullpath(index_id))

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

    async def check(self, hash, size=None):
        asset = self.objects.asset(hash)
        if not asset.exists():
            return False

        if size is not None:
            if asset.stat().st_size != size:
                return False

        computed_hash = await compute_hash(asset)
        return computed_hash == hash

    async def multicheck(self, files: Iterable[tuple[str, int | None]]):
        return await asyncio.gather(
            *map(lambda x: self.check(x[0], x[1]), files),
            return_exceptions=True
        )
