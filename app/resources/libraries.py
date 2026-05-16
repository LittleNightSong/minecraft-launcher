import os.path
from os import PathLike
from pathlib import Path

from app.common import compute_hash
from app.common.methods import trace
from app.resources.base import BaseDirectory


class Library:
    __slots__ = ['name', 'root', '_group', '_group_parts_o', '_artifact', '_version', '_classifier', '_ok', '_path']

    def __init__(self, name: str, root: PathLike[str] = None):
        self.name: str = name
        self.root: PathLike[str] | None = root

        self._group: str = None
        self._group_parts_o: list[str] = None
        self._artifact: str = None
        self._version: str = None
        self._classifier: str = None
        self._ok: bool = False
        self._path: str = None

    @property
    def _group_parts(self):
        self._generate_parts()
        if self._group_parts_o is None:
            self._group_parts_o = self._group.split('.')

        return self._group_parts_o

    def _generate_parts(self):
        if self._ok: return
        parts = self.name.split(':')
        if len(parts) == 3:
            self._group, self._artifact, self._version = parts

        elif len(parts) == 4:
            self._group, self._artifact, self._version, self._classifier = parts

        else:
            raise ValueError('Invalid library name', self.name)

        self._ok = True

    @property
    def path(self):
        if self._path:
            return self._path

        self._generate_parts()

        if self._classifier:
            filename = f'{self._artifact}-{self._version}-{self._classifier}.jar'

        else:
            filename = f'{self._artifact}-{self._version}.jar'

        path = os.path.join(
            *self._group_parts,
            self._artifact,
            self._version,
            filename
        )
        return path

    @property
    def fullpath(self):
        if not self.root:
            raise ValueError('Library root not set')
        return os.path.join(self.root, self.path)

    def __fspath__(self):
        return self.fullpath


class LibrariesDirectory(BaseDirectory):
    def __init__(self, path):
        self.path = Path(path)

    def library(self, name):
        return Library(name, self.path)

    # @trace
    async def check(self, name, hash, size=None):
        lib = self.library(name)
        if not os.path.exists(lib):
            return False

        if size is not None:
            if os.stat(lib).st_size != size:
                return False

        return await compute_hash(lib) == hash
